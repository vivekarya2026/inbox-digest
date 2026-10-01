# Inbox Digest Agent — Developer Guide

## What this project does

An ambient, scheduled, multi-tenant agent that:
1. Reads each registered user's unread Gmail inbox every hour.
2. Filters social, promotional, and bulk mail in code (no LLM cost).
3. Uses the user's own LLM key (Gemini / OpenAI / Anthropic via LiteLLM) to categorize and prioritize the remaining messages.
4. Sends a WhatsApp digest to the user **only when there are P1 or P2 items**.
5. Does nothing if the inbox is clear of important mail.

## Project structure

```
inbox-digest/
├── app/
│   ├── agent.py           ← Root agent: tools + LiteLLM BYOK + send gate
│   ├── auths.py           ← Gmail OAuth config (adapted from oauth-user-consent-flow recipe)
│   ├── config.py          ← Local dev defaults; BYOK model resolution
│   ├── digest.py          ← Pure-Python WhatsApp message formatter
│   ├── fast_api_app.py    ← Ambient FastAPI server + Pub/Sub trigger + state injection middleware
│   ├── observability.py   ← Structured logging for Cloud Trace/Logging/Monitoring
│   ├── tools/
│   │   ├── gmail.py       ← fetch_unread_emails + negotiate_creds() (three-stage OAuth)
│   │   └── whatsapp.py    ← send_whatsapp (Meta Cloud API or Twilio, env-toggled)
│   └── store/
│       └── user_store.py  ← Firestore-backed per-user config + KMS encryption
├── onboarding/
│   ├── main.py            ← Self-service sign-up web app (FastAPI + Jinja2)
│   └── templates/         ← HTML templates (index, setup, dashboard, success, error)
├── deployment/
│   └── terraform/
│       └── inbox-digest/  ← Cloud Run + Firestore + Pub/Sub + KMS + Monitoring + Scheduler
├── tests/
│   └── eval/
│       ├── eval_config.yaml      ← agents-cli eval metrics config
│       ├── response_quality.py   ← LLM-as-judge rubric (filter, priority, digest quality)
│       └── datasets/
│           └── basic-dataset.json ← 6 labelled inbox scenarios
└── .agents-cli-spec.md    ← Project spec (source of truth for design decisions)
```

## Key design decisions

| Decision | Choice | Why |
|----------|--------|-----|
| LLM for categorization | User's own key via LiteLLM | BYOK — users bring Gemini/OpenAI/Anthropic |
| Send gate | Hard code rule in `build_and_send_digest` | LLM can't override "don't send if empty" |
| Social/promo filter | Deterministic code (labels, headers, domain list) | Zero LLM cost for bulk exclusion |
| Token storage | Firestore + Cloud KMS | Encrypted at rest; never in logs |
| Hourly trigger | Cloud Scheduler → Pub/Sub → ADK ambient trigger | Scales to N users, one job per user |
| WhatsApp | Meta Business Cloud API (Twilio swappable via env) | Official API, free conversation tier |

## Running locally

```bash
# Install dependencies
cd inbox-digest
agents-cli install   # wraps uv sync

# Local playground (single-user, ADK Web UI, OAuth consent in browser)
agents-cli playground

# One-shot test (mock gmail token must be in .env or injected manually)
agents-cli run "Run the inbox digest for me"

# Run the ambient trigger server directly
uv run python -m app.fast_api_app

# Run the onboarding app
uv run python onboarding/main.py
```

## Eval

```bash
agents-cli eval run
```

Target scores (all must pass before deploying):
- `custom_response_quality` ≥ 0.8
- `silence_when_unimportant` = 1.0 (100% compliance)
- `sent_digest` = 1 for all non-silent cases

## Deploy

⚠️ **Do not deploy without explicit approval from the operator.**

```bash
# 1. Build and push container images
# 2. Set Terraform variable values in deployment/terraform/inbox-digest/terraform.tfvars
# 3. Apply:
cd deployment/terraform/inbox-digest
terraform init
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars  ← requires operator approval
```

## Adding a new email provider (non-Gmail)

The Gmail tool is in `app/tools/gmail.py`. The OAuth config is in `app/auths.py`.
To add Outlook/IMAP: replace `fetch_unread_emails` with a new tool, keep the same
return schema (`{"status", "emails", "total_fetched", "total_after_filter"}`).
The agent, formatter, and WhatsApp adapter are provider-agnostic.

## Recipes this project adapts

- [`oauth-user-consent-flow`](https://github.com/google/adk-samples/tree/main/core/python/oauth-user-consent-flow) — `negotiate_creds()` three-stage OAuth pattern
- [`ambient-expense-agent`](https://github.com/google/adk-samples/tree/main/core/python/ambient-expense-agent) — Pub/Sub ambient trigger, rules-in-code + LLM-for-judgment, structured logging
