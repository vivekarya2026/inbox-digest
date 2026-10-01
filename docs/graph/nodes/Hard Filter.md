---
aliases: ["hard filter", "promo filter", "social filter", "bulk sender filter"]
tags: [concept/design, project/inbox-digest]
---

# 🧹 Hard Filter

**Deterministic code-level exclusion of noise before the LLM ever sees a message.**

## Rules (in execution order)

| # | Rule | Mechanism | Cost |
|---|------|-----------|------|
| 1 | INBOX only, unread only | Gmail query `is:unread in:INBOX` | API call |
| 2 | Gmail label exclusion | `CATEGORY_PROMOTIONS`, `CATEGORY_SOCIAL`, `CATEGORY_FORUMS` | O(1) per message |
| 3 | List-Unsubscribe header | Header presence check | O(1) per message |
| 4 | Bulk sender domain | frozenset of 25+ domains | O(1) per message |
| 5 | De-duplication | `seen_message_ids` rolling set (max 5000) | O(1) per message |

Zero LLM cost for all five rules. An email that fails any rule never reaches the categorisation step.

## Design consequence

Fewer emails → cheaper LLM calls → faster runs. Most inboxes are 80%+ noise, so the LLM typically sees only 2–5 emails per run.

## Where it lives

- Rules 1–4: [[gmail_tool]] `_should_exclude()`
- Rule 5: [[gmail_tool]] `fetch_unread_emails()` main body

## Related

- [[gmail_tool]]
- [[Categorisation Rubric]]
- [[Send Gate]]
