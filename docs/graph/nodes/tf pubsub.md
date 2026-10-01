---
aliases: ["tf/pubsub.tf", "Pub/Sub terraform"]
tags: [infra/terraform, layer/infra, project/inbox-digest]
file: deployment/terraform/inbox-digest/pubsub.tf
---

# 📨 tf pubsub

Provisions the [[Pub Sub]] topic, push subscription, and dead-letter topic.

## Resources

| Resource | Terraform ID |
|----------|-------------|
| Trigger topic | `google_pubsub_topic.triggers` |
| Dead-letter topic | `google_pubsub_topic.dead_letter` |
| Push subscription | `google_pubsub_subscription.trigger_push` |

## Push subscription details

- Endpoint: `${agent.uri}/apps/app/trigger/pubsub`
- OIDC: `pubsub_invoker` SA
- Ack deadline: 60s
- Retry: 10s–300s exponential backoff
- Dead-letter after 3 attempts → picked up by [[tf monitoring]] alert

## Depends on

- [[tf main]] — `google_project_service.apis`
- [[tf service]] — `google_cloud_run_v2_service.agent.uri`
- [[tf iam]] — `google_service_account.pubsub_invoker`
