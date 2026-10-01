---
aliases: ["tf/service.tf", "Cloud Run terraform", "Secret Manager terraform"]
tags: [infra/terraform, layer/infra, project/inbox-digest]
file: deployment/terraform/inbox-digest/service.tf
---

# ☁️ tf service

Cloud Run services + Secret Manager secrets.

## Secret Manager resources

| Secret ID | Used by | Injected as |
|-----------|---------|-------------|
| `whatsapp-api-token` | [[agent_service]] | `WHATSAPP_API_TOKEN` |
| `whatsapp-phone-number-id` | [[agent_service]] | `WHATSAPP_PHONE_NUMBER_ID` |
| `onboarding-session-secret` | [[onboarding_service]] | `SESSION_SECRET` |
| `google-oauth-client-secret` | [[onboarding_service]] | `GOOGLE_CLIENT_SECRET` |

## Cloud Run: agent backend

| Config | Value |
|--------|-------|
| Name | `inbox-digest-agent` |
| Ingress | `INGRESS_TRAFFIC_INTERNAL_ONLY` (Pub/Sub only) |
| Min instances | 1 (always warm, avoids cold-start timeouts) |
| Max instances | 10 |
| SA | `inbox-digest-agent` (from [[tf iam]]) |
| Startup probe | `GET /health` |

## Cloud Run: onboarding web app

| Config | Value |
|--------|-------|
| Name | `inbox-digest-onboarding` |
| Ingress | `INGRESS_TRAFFIC_ALL` (public web) |
| Min instances | 0 (scales to zero) |
| Max instances | 5 |
| SA | `inbox-digest-onboarding` (from [[tf iam]]) |
| IAM | `allUsers` → `run.invoker` (public access) |

## Depends on

- [[tf main]] — KMS key ID
- [[tf iam]] — service accounts
- [[tf pubsub]] — `agent.uri` referenced by push subscription
