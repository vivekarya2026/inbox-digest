---
aliases: ["app/digest.py", "format_digest"]
tags: [module/app, layer/formatter, project/inbox-digest]
file: app/digest.py
---

# 📝 digest

`format_digest(emails, run_timestamp)` — pure Python WhatsApp message builder.

## Responsibilities

- Receives the LLM-categorised email list (P1/P2 only — caller pre-filters)
- Renders a structured text message with emoji markers, sender, subject, summary, action hint
- Enforces the 4096-char WhatsApp limit (truncates gracefully)
- Returns a plain string — zero side effects

## Output format (example)

```
📬 *Inbox Digest* — 14:00 UTC
📊 1 urgent · 2 important

━━━ 🔴 URGENT ━━━
🔴 1. Server outage — need your response NOW
   ✅ From: ops@yourcompany.com
   Production is down, blocked on your config change.
   ➡️ Reply immediately

━━━ 🟡 IMPORTANT ━━━
🟡 2. Invoice #2026-089 due in 3 days
   💰 From: billing@cloudprovider.io
   $1,240 invoice due Oct 3.
   ➡️ Review and pay

─────────────────
📥 3 email(s) need your attention.
```

## Emoji legend

| Emoji | Meaning |
|-------|---------|
| 🔴 | P1 — urgent |
| 🟡 | P2 — important |
| ✅ | action_needed |
| 💬 | awaiting_reply |
| 💰 | financial_legal |
| 📅 | scheduling_calendar |
| ℹ️ | informational |
| 👤 | personal |

## Depends on

- stdlib only (`datetime`)

## Called by

- [[agent]] — `build_and_send_digest()` before [[whatsapp_tool]]
