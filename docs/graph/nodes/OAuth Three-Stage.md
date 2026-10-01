---
aliases: ["OAuth three-stage", "negotiate_creds", "credential negotiation"]
tags: [concept/design, project/inbox-digest]
---

# 🔄 OAuth Three-Stage

The `negotiate_creds(tool_context)` pattern from `core/python/oauth-user-consent-flow`.  
Handles Gmail OAuth tokens across three distinct runtime environments without code changes.

## Three stages

```
Stage 1 — Cached/injected token
  tool_context.state[TOKEN_CACHE_KEY]  or  state["temp:{TOKEN_CACHE_KEY}"]
  ↓ Found + valid? Return Credentials immediately.
  ↓ Found + expired? Refresh, re-cache, return.
  ↓ Not found → Stage 2

Stage 2 — ADK auth response (local ADK Web UI dev only)
  tool_context.get_auth_response(AUTH_CONFIG)
  ↓ Present? Build Credentials, cache in state, return.
  ↓ Not present → Stage 3

Stage 3 — Initiate consent (local dev only)
  tool_context.request_credential(AUTH_CONFIG)
  ↓ Returns {"pending": True} — ADK will show OAuth popup to developer.
```

## Production path (ambient scheduler)

Only Stage 1 is ever reached. [[fast_api_app]] injects the decrypted Firestore token into `tool_context.state[TOKEN_CACHE_KEY]` before the agent run starts. Stages 2 and 3 are dead code in production.

## Local dev path

All three stages may be reached:
- First run: Stage 3 (consent popup in ADK Web UI)
- After consent: Stage 2 (exchange)
- Subsequent runs: Stage 1 (cached in state)

## Related

- [[auths]] — `TOKEN_CACHE_KEY`, `AUTH_CONFIG`, `SCOPES`
- [[gmail_tool]] — `negotiate_creds()` implementation
- [[fast_api_app]] — injects token into state (production)
- [[Google OAuth]] — external provider
