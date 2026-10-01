---
aliases: ["app/observability.py", "structured logging", "Cloud Logging"]
tags: [module/app, layer/observability, project/inbox-digest]
file: app/observability.py
---

# 📊 observability

Structured JSON logging helpers. Cloud Run captures `stdout` as Cloud Logging entries automatically — no SDK required.

## Log event catalogue

| Function | `event` field | Severity | Triggers alert? |
|----------|--------------|----------|-----------------|
| `log_run_start` | `digest_run_start` | INFO | No |
| `log_run_complete` | `digest_run_complete` | INFO | No |
| `log_digest_sent` | `digest_sent` | INFO | No |
| `log_digest_skipped` | `digest_skipped` | INFO | No |
| `log_send_failed` | `digest_send_failed` | WARNING | **Yes** → [[tf monitoring]] |
| `log_needs_reauth` | `needs_reauth` | WARNING | No (future) |
| `log_error` | `digest_error` | ERROR | No (future) |

## Log entry schema

```json
{
  "severity": "INFO",
  "service": "inbox-digest-agent",
  "version": "cloud-run-revision-id",
  "event": "digest_sent",
  "user_id": "google-sub-id",
  "timestamp": "2026-09-30T14:00:01Z",
  "p1_count": 1,
  "p2_count": 2,
  "provider": "meta",
  "message_id": "wamid.xxx"
}
```

## Alert trigger

`digest_send_failed` → matched by log-based metric `inbox_digest/send_failed` in [[tf monitoring]] → fires `inbox-digest-agent` alert policy.

## Used by

- [[agent]] — `build_and_send_digest()` logs every delivery outcome
- [[fast_api_app]] — (indirectly via agent)
