---
aliases: ["send gate", "P1/P2 gate", "no-send rule", "silence when empty"]
tags: [concept/design, project/inbox-digest]
---

# 🚫 Send Gate

**Hard rule: never send a WhatsApp digest if there are zero P1 or P2 emails.**

## Two layers of enforcement

| Layer | Where | What |
|-------|-------|------|
| LLM instruction | [[agent]] `_SYSTEM_INSTRUCTION` | "Do NOT call build_and_send_digest if no emails" |
| Code guard | [[agent]] `build_and_send_digest()` | `if len(p1_p2) < config.min_important_to_send: return {skipped}` |

The code check is the real gate. The LLM instruction reduces unnecessary tool calls.

## Why two layers?

LLMs can hallucinate or misfollow instructions. The code check is deterministic — it cannot be bypassed by a model generating unexpected text. This is the "only alert on condition" pattern from the `ambient-expense-agent` recipe.

## Configuration

`MIN_IMPORTANT_TO_SEND` env var (default: `1`). Could be set to `2` for a user who only wants digests when there are two or more important emails.

## Related

- [[Categorisation Rubric]] — what makes an email P1 or P2
- [[agent]]
- [[digest]]
