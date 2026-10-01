---
aliases: ["agent service", "Cloud Run agent", "inbox-digest-agent service"]
tags: [service/agent, layer/cloud-run, project/inbox-digest]
---

# ☁️ agent_service

Cloud Run service `inbox-digest-agent`. The ADK ambient agent backend.

## Configuration

| Config | Value |
|--------|-------|
| Ingress | `INTERNAL_ONLY` — only [[Pub Sub]] push can reach it |
| Min instances | 1 (always warm — avoids 60s ack timeout on cold start) |
| Max instances | 10 |
| SA | `inbox-digest-agent` |
| Port | 8080 |

## Entrypoint

[[fast_api_app]] — `uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8080`

## Secrets injected at deploy time

| Env var | Source |
|---------|--------|
| `WHATSAPP_API_TOKEN` | Secret Manager |
| `WHATSAPP_PHONE_NUMBER_ID` | Secret Manager |
| `GOOGLE_KMS_KEY_NAME` | Terraform var |

## Provisioned by

- [[tf service]]
- [[tf iam]]

## Receives traffic from

- [[Pub Sub]] push subscription (OIDC authenticated)
