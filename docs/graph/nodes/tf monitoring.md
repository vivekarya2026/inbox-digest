---
aliases: ["tf/monitoring.tf", "Cloud Monitoring terraform", "alerts"]
tags: [infra/terraform, layer/infra, project/inbox-digest]
file: deployment/terraform/inbox-digest/monitoring.tf
---

# 📈 tf monitoring

Cloud Monitoring log-based metrics and alert policies.

## Log-based metrics

| Metric | Filter | Fired by |
|--------|--------|---------|
| `inbox_digest/dead_letter_messages` | Pub/Sub dead-letter subscription | [[Pub Sub]] delivery failure |
| `inbox_digest/send_failed` | `jsonPayload.event="digest_send_failed"` on agent Cloud Run | [[observability]] `log_send_failed()` |

## Alert policies

| Policy | Fires when | Notifies |
|--------|-----------|---------|
| Dead-letter messages > 0 | Any message lands in dead-letter | `notification_email` |
| WhatsApp send failures > 0 | Any `digest_send_failed` log | `notification_email` |

Both policies: severity `WARNING`, threshold 0, period 60s.

## Notification channel

`google_monitoring_notification_channel.ops_email` → email to `var.notification_email`

## Depends on

- [[tf main]] — `google_project_service.apis`
- [[tf pubsub]] — dead-letter subscription name
- [[tf service]] — agent service name (filter label)
- [[observability]] — emits `digest_send_failed` event that triggers the metric
