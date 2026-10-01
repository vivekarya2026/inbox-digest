---
aliases: ["categorisation", "priority rubric", "P1 P2 P3", "email priority"]
tags: [concept/design, project/inbox-digest]
---

# 🏷️ Categorisation Rubric

**The LLM judgment layer** — applied to emails that survive the [[Hard Filter]].

## Categories

| Category | Meaning |
|----------|---------|
| `action_needed` | Requires a reply or decision from the user |
| `awaiting_reply` | User sent something; a response or nudge arrived |
| `financial_legal` | Invoices, contracts, compliance, bank statements |
| `scheduling_calendar` | Meeting invites, rescheduling, RSVP requests |
| `informational` | FYI updates — no action needed |
| `personal` | Friends, family, non-work personal |

## Priority levels

| Priority | Definition | Included in digest? |
|----------|-----------|---------------------|
| P1 | **Urgent AND directed specifically at the user** — "blocked on you", "reply by EOD", today's meeting invite | ✅ Yes (🔴) |
| P2 | **Important, not time-sensitive** — project update needing eventual reply, invoice not yet due | ✅ Yes (🟡) |
| P3 | **Low signal** — no action needed, or FYI-only | ❌ No (default) |

## P1 signals

- "please review by EOD", "waiting on you", "blocked"
- Today's meeting invite needing confirmation
- "urgent", "ASAP", "immediately"
- Specific deadline within 24h

## P2 signals

- Follow-ups, project updates requiring a reply
- Deadlines > 24h away
- Invoices not yet due
- Contract renewals with future deadline

## P3 signals (even after passing [[Hard Filter]])

- Newsletters/digests that slipped through
- General company announcements
- "FYI" updates with no required action

## Applied by

- [[agent]] `_SYSTEM_INSTRUCTION` — the LLM reads this rubric
- [[Send Gate]] — consumes the output (P1+P2 count)
- [[digest]] — renders P1/P2 items into WhatsApp message
