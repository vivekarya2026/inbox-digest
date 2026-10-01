---
aliases: ["multi-tenant", "per-user store", "tenant isolation"]
tags: [concept/design, project/inbox-digest]
---

# 🏢 Multi-Tenant Store

**Pattern: one Firestore document per user, all secrets encrypted with [[Cloud KMS]].**

## Isolation properties

| Property | Mechanism |
|----------|-----------|
| Token isolation | Gmail OAuth token stored per `user_id`, never shared |
| Key isolation | LLM API key encrypted per user, decrypted only for their run |
| Run isolation | One [[Cloud Scheduler]] job per user — failures don't cascade |
| Seen-ID isolation | `seen_message_ids` scoped to the user's document |

## Data flow on each hourly run

```
Cloud Scheduler (user-specific job)
  → Pub/Sub message with user_id
  → fast_api_app middleware
  → UserStore.get_agent_state(user_id)     ← Firestore read
  → KMS.decrypt(gmail_token_encrypted)     ← KMS decrypt
  → KMS.decrypt(llm_api_key_encrypted)     ← KMS decrypt
  → inject into ADK session state
  → agent run with user's credentials
  → UserStore.update_seen_ids(user_id, ...) ← Firestore write
```

## Scalability

- Firestore scales horizontally — N users = N documents, no schema change
- Each user's Pub/Sub message is processed independently in parallel
- Cloud Run autoscales to handle burst of simultaneous user runs (each hour)

## Related

- [[user_store]]
- [[Cloud Scheduler]]
- [[Pub Sub]]
- [[Cloud Firestore]]
- [[Cloud KMS]]
- [[fast_api_app]]
