---
aliases: ["Gmail API v1", "google-api-python-client gmail"]
tags: [external/api, project/inbox-digest]
---

# 📧 Gmail API

Google Gmail REST API v1. Used by [[gmail_tool]] to read the user's inbox.

## Methods used

| Method | What it does |
|--------|-------------|
| `users.messages.list` | `q="is:unread in:INBOX"` — get message IDs |
| `users.messages.get` | `format="full"` — get headers, labels, body for one message |

## Rate limits

- 250 quota-units/user/second
- `messages.list` = 5 units; `messages.get` = 5 units
- 100 `messages.get` per batch (implemented in [[gmail_tool]])

## Scope

`https://www.googleapis.com/auth/gmail.readonly`

Read-only. The agent **never** calls any mutating method (`send`, `modify`, `delete`, `trash`). Enforced by scope restriction at the OAuth consent level.

## Auth flow

Managed by [[OAuth Three-Stage]] via [[auths]].

## Used by

- [[gmail_tool]]
