---
aliases: ["Cloud Scheduler", "hourly scheduler", "cron job"]
tags: [infra/gcp, layer/trigger, project/inbox-digest]
---

# ⏰ Cloud Scheduler

GCP managed cron service. Creates one job **per registered user** during [[onboarding_service]] setup.

## Job spec

| Field | Value |
|-------|-------|
| Schedule | `0 * * * *` (every hour, UTC) |
| Target | [[Pub Sub]] topic `inbox-digest-triggers` |
| Auth | OIDC token — `inbox-digest-pubsub-invoker` SA |
| Payload | `{"subscription": "projects/…/subscriptions/{user_id}"}` |

## Fan-out pattern

Each user gets their own Scheduler job. The job name is `inbox-digest-{user_id}`.  
This keeps runs isolated — one user's failure doesn't block others.

## Created by

- [[onboarding_service]] — `_register_scheduler_job(user_id)` on setup

## Flows to

- [[Pub Sub]] → [[fast_api_app]] → [[agent]]

## Provisioned by

- [[tf pubsub]] — topic and push subscription
- [[tf iam]] — `pubsub_invoker` SA + `cloudscheduler.admin` role for onboarding SA
