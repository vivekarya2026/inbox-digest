---
aliases: ["fast_api_app.py", "ambient trigger", "trigger endpoint"]
tags: [module/app, layer/server, project/inbox-digest]
file: app/fast_api_app.py
---

# 🚀 fast_api_app

**FastAPI ambient server** — the Cloud Run entrypoint for the agent backend.

## Responsibilities

1. Mounts the ADK web server with `trigger_sources=["pubsub"]`
2. Middleware: normalises Pub/Sub subscription paths → short `user_id`
3. Middleware: loads per-user config from [[user_store]] and injects into trigger payload `initialState`
4. Exposes `/health` endpoint
5. Starts `uvicorn` on `PORT` (default 8080)

## Trigger flow

[[Cloud Scheduler]] → [[Pub Sub]] → **POST /apps/app/trigger/pubsub** → middleware → [[agent]]

## State injected into each run

```json
{
  "user_id": "google-sub-id",
  "gmail_token": { ... },          // → TOKEN_CACHE_KEY for [[auths]]
  "gmail-oauth": { ... },          // duplicate key for negotiate_creds()
  "whatsapp_number": "+1...",
  "user_config": {
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "llm_api_key": "sk-..."        // in-memory only — see [[BYOK LiteLLM]]
  },
  "seen_message_ids": [...]         // de-dup — see [[Hard Filter]]
}
```

## Depends on

- [[user_store]] — `UserStore.get_agent_state(user_id)`
- [[agent]] — ADK root_agent (discovered via `agents_dir`)

## Deployed by

- [[tf service]] — Cloud Run `inbox-digest-agent` (internal ingress)
