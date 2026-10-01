---
aliases: ["app/store/user_store.py", "UserStore", "Firestore store"]
tags: [module/store, layer/persistence, project/inbox-digest]
file: app/store/user_store.py
---

# 🗄️ user_store

`UserStore` — Firestore-backed per-user config, [[Multi-Tenant Store]] pattern.

## Firestore document schema

Path: `/users/{user_id}`

```json
{
  "gmail_token_encrypted": "<KMS-encrypted bytes>",
  "whatsapp_number": "+14155551234",
  "llm_provider": "openai",
  "llm_model": "gpt-4o-mini",
  "llm_api_key_encrypted": "<KMS-encrypted bytes>",
  "seen_message_ids": ["msg001", "msg002"],
  "last_run_at": "2026-09-30T14:00:00Z",
  "active": true,
  "needs_reauth": false
}
```

## Key methods

| Method | What it does |
|--------|-------------|
| `create_or_update_user(...)` | Encrypt token + API key → write Firestore doc |
| `get_agent_state(user_id)` | Decrypt secrets → return state dict for [[fast_api_app]] injection |
| `update_seen_ids(user_id, ids)` | Persist de-dup window after each run |
| `mark_needs_reauth(user_id)` | Set `needs_reauth=true` on 401 from [[gmail_tool]] |
| `list_active_users()` | Return active, reauth-ok user IDs |

## KMS encryption

- `_kms_encrypt(plaintext)` / `_kms_decrypt(ciphertext)` — uses [[Cloud KMS]]
- Falls back to base64 if `KMS_ENABLED=false` (local dev)
- Key name from `GOOGLE_KMS_KEY_NAME` env var

## Local dev fallback

If `FIRESTORE_ENABLED=false` or `google-cloud-firestore` unavailable → in-memory dict `_local_store`.

## Depends on

- [[Cloud Firestore]]
- [[Cloud KMS]]

## Used by

- [[fast_api_app]] — `get_agent_state()` per Pub/Sub trigger
- [[onboarding_service]] — `create_or_update_user()` on setup form submit
