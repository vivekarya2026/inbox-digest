---
aliases: ["KMS", "Cloud KMS", "key management", "encryption"]
tags: [infra/gcp, layer/security, project/inbox-digest]
---

# 🔐 Cloud KMS

GCP Cloud Key Management Service. Encrypts Gmail OAuth tokens and user LLM API keys before storage in [[Cloud Firestore]].

## Key config

| Attribute | Value |
|-----------|-------|
| Location | `global` |
| Keyring | `inbox-digest-keyring` |
| Key | `user-secrets` |
| Rotation period | 90 days |
| `prevent_destroy` | `true` (Terraform lifecycle) |

## What is encrypted

| Field | Encrypted with |
|-------|---------------|
| `gmail_token_encrypted` | KMS symmetric encryption |
| `llm_api_key_encrypted` | KMS symmetric encryption |

WhatsApp number and LLM provider/model are stored plaintext (not secrets).

## Access

Only the two Cloud Run SAs can encrypt/decrypt ([[tf iam]]):
- `inbox-digest-agent` — decrypt during agent runs
- `inbox-digest-onboarding` — encrypt during user onboarding

## Local dev fallback

When `KMS_ENABLED=false`, [[user_store]] uses base64 as a no-op placeholder. Never use in production.

## Provisioned by

- [[tf main]]

## Used by

- [[user_store]] — `_kms_encrypt()`, `_kms_decrypt()`
