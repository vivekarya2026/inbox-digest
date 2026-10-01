---
aliases: ["app/auths.py", "OAuth config", "TOKEN_CACHE_KEY", "AUTH_CONFIG"]
tags: [module/app, layer/auth, project/inbox-digest]
file: app/auths.py
---

# 🔑 auths

Gmail OAuth 2.0 configuration. Adapted from `core/python/oauth-user-consent-flow/app/auths.py`.

## Key exports

| Symbol | Value | Used by |
|--------|-------|---------|
| `SCOPES` | `{gmail.readonly: ...}` | [[gmail_tool]] |
| `TOKEN_CACHE_KEY` | `os.env("AUTH_ID", "gmail-oauth")` | [[gmail_tool]] negotiate_creds |
| `AUTH_SCHEME` | `OAuth2(authorizationCode(...))` | ADK auth flow (local dev) |
| `AUTH_CREDENTIAL` | `AuthCredential(OAUTH2, client_id, secret)` | ADK auth flow (local dev) |
| `AUTH_CONFIG` | `AuthConfig(scheme, credential)` | [[gmail_tool]] negotiate_creds stage 3 |

## Scope

```python
SCOPES = {
    "https://www.googleapis.com/auth/gmail.readonly": "Gmail API (read-only)",
}
```

Gmail read-only: list + read messages. **Never** send, modify, or delete.

## Usage paths

| Path | What uses auths |
|------|-----------------|
| Ambient scheduler | `TOKEN_CACHE_KEY` only — token injected by [[fast_api_app]] |
| Local ADK Web UI dev | `AUTH_CONFIG` — triggers consent flow in browser |

## Related

- [[OAuth Three-Stage]]
- [[gmail_tool]]
- [[Google OAuth]]
