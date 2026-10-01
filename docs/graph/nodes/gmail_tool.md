---
aliases: ["tools/gmail.py", "fetch_unread_emails", "negotiate_creds"]
tags: [module/tools, layer/tool, project/inbox-digest]
file: app/tools/gmail.py
---

# 📧 gmail_tool

`fetch_unread_emails()` + `negotiate_creds()` — the Gmail read tool.

## Responsibilities

1. **`negotiate_creds(tool_context)`** — [[OAuth Three-Stage]] resolution:
   - Stage 1: check `tool_context.state[TOKEN_CACHE_KEY]` (cached or injected by [[fast_api_app]])
   - Stage 2: exchange ADK auth response (local dev only)
   - Stage 3: initiate consent flow (local dev only)

2. **`fetch_unread_emails(tool_context)`** — main tool:
   - Queries `is:unread in:INBOX` (max 100)
   - Applies [[Hard Filter]] (labels, List-Unsubscribe, bulk domain list)
   - Skips `seen_message_ids` (de-duplication)
   - Returns `{"status", "emails", "total_fetched", "total_after_filter"}`

## [[Hard Filter]] rules (no LLM cost)

| Rule | Mechanism |
|------|-----------|
| Gmail label exclusion | `CATEGORY_PROMOTIONS`, `CATEGORY_SOCIAL`, `CATEGORY_FORUMS` |
| Bulk-sender header | `List-Unsubscribe` present |
| Domain blocklist | 25+ known bulk-sender domains (frozenset) |
| De-duplication | `seen_message_ids` rolling window (max 5000) |

## Depends on

- [[auths]] — `TOKEN_CACHE_KEY`, `AUTH_CONFIG`, `SCOPES`
- [[Gmail API]] — `googleapiclient.discovery.build("gmail", "v1")`

## Called by

- [[agent]] — first tool in every hourly run
