---
aliases: ["tf/main.tf", "terraform main", "deployment/terraform/inbox-digest/main.tf"]
tags: [infra/terraform, layer/infra, project/inbox-digest]
file: deployment/terraform/inbox-digest/main.tf
---

# 🏗️ tf main

Root Terraform file. Enables GCP APIs, provisions [[Cloud Firestore]], and creates the [[Cloud KMS]] keyring + key.

## Resources

| Resource | ID |
|----------|----|
| GCP APIs (11) | `google_project_service.apis` |
| Firestore database | `google_firestore_database.inbox_digest` (native mode) |
| KMS keyring | `google_kms_key_ring.inbox_digest` (global location) |
| KMS crypto key | `google_kms_crypto_key.user_secrets` (90-day rotation) |

## APIs enabled

`run`, `pubsub`, `cloudscheduler`, `firestore`, `cloudkms`, `secretmanager`, `cloudtrace`, `logging`, `monitoring`, `cloudresourcemanager`, `iam`

## Depends on / used by

- [[tf iam]] — references `google_kms_crypto_key.user_secrets`
- [[tf service]] — references KMS key ID for Cloud Run env vars
- [[tf monitoring]] — depends on `google_project_service.apis`

## `lifecycle { prevent_destroy = true }`

Applied to the KMS key — prevents accidental Terraform destroy from losing all encrypted user secrets.
