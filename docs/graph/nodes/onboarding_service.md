---
aliases: ["onboarding/main.py", "sign-up app", "self-service onboarding"]
tags: [service/onboarding, layer/web, project/inbox-digest]
file: onboarding/main.py
---

# 🌐 onboarding_service

Self-service sign-up FastAPI web app. Runs as a separate Cloud Run service (public ingress).

## User journey

```
GET  /             → landing page (Sign in with Google)
GET  /auth/login   → redirect to Google OAuth consent
GET  /auth/callback→ exchange code → store token → show setup form
POST /setup        → save WhatsApp + LLM key → register Cloud Scheduler job
GET  /dashboard    → current settings + last-run status
POST /deactivate   → pause user's hourly job
```

## OAuth flow

1. Redirects to [[Google OAuth]] consent (`gmail.readonly` + `openid email profile`)
2. Callback exchanges code for `gmail_token`
3. Stores token (encrypted) in [[user_store]] via `create_or_update_user()`

## Scheduler registration

On `POST /setup` → calls `google.cloud.scheduler_v1` to create a per-user job:
- Schedule: `0 * * * *` (every hour, UTC)
- Target: [[Pub Sub]] topic `inbox-digest-triggers`
- Message payload: `{"subscription": "projects/PROJECT/subscriptions/{user_id}"}`

## Templates

- `index.html` — landing, "Sign in with Google" button
- `setup.html` — WhatsApp number + LLM provider/model/key form
- `success.html` — confirmation + scheduler status
- `dashboard.html` — settings overview, pause button
- `error.html` — error state

## Depends on

- [[user_store]] — `create_or_update_user()`, `get_user()`
- [[Google OAuth]] — authorization code flow
- `google.cloud.scheduler_v1` — Cloud Scheduler job creation

## Deployed by

- [[tf service]] — Cloud Run `inbox-digest-onboarding` (public ingress)
- [[tf iam]] — `onboarding_sa` service account
