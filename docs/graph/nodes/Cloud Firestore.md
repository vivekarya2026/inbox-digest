---
aliases: ["Cloud Firestore", "Firestore", "NoSQL database"]
tags: [infra/gcp, layer/persistence, project/inbox-digest]
---

# 🗃️ Cloud Firestore

GCP managed NoSQL document database. Stores one document per user in the `users` collection.

## Collection structure

```
/users/
  {google-sub-id}/
    gmail_token_encrypted: bytes
    whatsapp_number: string
    llm_provider: string
    llm_model: string
    llm_api_key_encrypted: bytes
    seen_message_ids: array<string>
    last_run_at: timestamp
    active: bool
    needs_reauth: bool
```

## Access pattern

| Operation | Frequency | Called by |
|-----------|-----------|-----------|
| Read user doc | Once per hourly run | [[fast_api_app]] → [[user_store]] |
| Write seen_ids + last_run | Once per completed run | [[agent]] → [[user_store]] |
| Create/update user | Once at onboarding | [[onboarding_service]] → [[user_store]] |
| List active users | Rare (admin/debug) | [[user_store]] `list_active_users()` |

## Mode

Native mode (not Datastore mode). Provisioned by [[tf main]].

## Security

Firestore documents are only accessible by the two Cloud Run service accounts ([[tf iam]]).  
All secret fields are [[Cloud KMS]]-encrypted before write — Firestore access alone is not enough to read user secrets.

## Used by

- [[user_store]]
