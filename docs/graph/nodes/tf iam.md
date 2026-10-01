---
aliases: ["tf/iam.tf", "service accounts", "IAM roles"]
tags: [infra/terraform, layer/infra, project/inbox-digest]
file: deployment/terraform/inbox-digest/iam.tf
---

# 🔐 tf iam

Service accounts and IAM role bindings.

## Service accounts

| SA | Display name | Used by |
|----|-------------|---------|
| `inbox-digest-agent` | Agent backend SA | [[agent_service]] Cloud Run |
| `inbox-digest-onboarding` | Onboarding web app SA | [[onboarding_service]] Cloud Run |
| `inbox-digest-pubsub-invoker` | Pub/Sub → Cloud Run invoker | [[Pub Sub]] push auth |

## IAM bindings

| Who | Role | What |
|-----|------|------|
| agent SA | `datastore.user` | Read/write [[Cloud Firestore]] |
| agent SA | `cloudkms.cryptoKeyEncrypterDecrypter` | Encrypt/decrypt via [[Cloud KMS]] |
| agent SA | `cloudtrace.agent` | Write Cloud Trace spans |
| agent SA | `logging.logWriter` | Write [[observability]] logs |
| onboarding SA | `datastore.user` | Write [[user_store]] |
| onboarding SA | `cloudkms.cryptoKeyEncrypterDecrypter` | Encrypt user secrets |
| onboarding SA | `cloudscheduler.admin` | Create [[Cloud Scheduler]] jobs |
| pubsub invoker SA | `run.invoker` | Invoke [[fast_api_app]] on Cloud Run |
| pubsub invoker SA | `pubsub.publisher` | Publish to [[Pub Sub]] topic |
| Pub/Sub service agent | `iam.serviceAccountTokenCreator` | Create OIDC tokens for push |

## Depends on

- [[tf main]] — references KMS key, project
- [[tf service]] — references Cloud Run service for `run.invoker` binding
