---
aliases: ["Google OAuth 2.0", "OAuth consent", "accounts.google.com"]
tags: [external/api, layer/auth, project/inbox-digest]
---

# 🔑 Google OAuth

Google OAuth 2.0 authorization code flow. Used in two contexts:

## Context 1: Agent Gmail access ([[OAuth Three-Stage]])

- Scope: `gmail.readonly`
- Initiated: [[onboarding_service]] `/auth/login` → consent screen
- Token stored: [[user_store]] (KMS-encrypted)
- Used by: [[gmail_tool]] `negotiate_creds()`

## Context 2: User identity in onboarding

- Scopes: `openid email profile gmail.readonly` (combined)
- Used to: identify the user via `sub` claim (Google sub = Firestore doc ID)

## OAuth endpoints

| Endpoint | URL |
|----------|-----|
| Authorization | `https://accounts.google.com/o/oauth2/v2/auth` |
| Token exchange | `https://oauth2.googleapis.com/token` |
| User info | `https://www.googleapis.com/oauth2/v3/userinfo` |

## Credentials (operator-held)

| Env var | Description |
|---------|-------------|
| `GOOGLE_CLIENT_ID` | OAuth 2.0 web app client ID |
| `GOOGLE_CLIENT_SECRET` | OAuth 2.0 web app client secret (Secret Manager) |

## Used by

- [[onboarding_service]] — authorization code flow
- [[auths]] — OAuth scheme + credential definitions
- [[gmail_tool]] — `negotiate_creds()` stages 2–3
