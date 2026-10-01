---
aliases: ["Pub/Sub", "pubsub", "inbox-digest-triggers"]
tags: [infra/gcp, layer/messaging, project/inbox-digest]
---

# 📨 Pub Sub

GCP Pub/Sub topic `inbox-digest-triggers` — the message bus between [[Cloud Scheduler]] and [[fast_api_app]].

## Resources

| Resource | Name |
|----------|------|
| Topic | `inbox-digest-triggers` |
| Push subscription | `inbox-digest-triggers-push` |
| Dead-letter topic | `inbox-digest-triggers-dead-letter` |

## Push subscription config

- Endpoint: `{agent_service_uri}/apps/app/trigger/pubsub`
- Auth: OIDC token (`pubsub_invoker` SA)
- Ack deadline: 60 seconds (each user run must complete within 60s)
- Retry: 10s → 300s exponential backoff
- Dead-letter after 3 failed attempts → alerts [[tf monitoring]]

## Message format

```json
{
  "subscription": "projects/PROJECT/subscriptions/{user_id}",
  "user_id": "google-sub-id"
}
```

The `subscription` field value is used as the ADK session `user_id` after normalisation by [[fast_api_app]] middleware.

## Provisioned by

- [[tf pubsub]]

## Flows from

- [[Cloud Scheduler]]

## Flows to

- [[fast_api_app]]
