---
aliases: ["eval dataset", "basic-dataset.json", "inbox scenarios"]
tags: [eval, project/inbox-digest]
file: tests/eval/datasets/basic-dataset.json
---

# 📋 eval dataset

`tests/eval/datasets/basic-dataset.json` — 6 labelled inbox scenarios for [[eval config]].

## Cases

| ID | Scenario | Expected |
|----|----------|---------|
| `case_01_urgent_and_promo` | 1 urgent (server outage P1) + 1 promo + 1 social + 1 invoice (P2) | send=true, p1=1, p2=1 |
| `case_02_all_noise` | Newsletter + Instagram notification + GitHub stars | send=false (silence) |
| `case_03_meeting_today` | Today's meeting invite (P1) + design review (P2) + team lunch | send=true, p1≥1 |
| `case_04_personal_and_financial` | Netflix payment warning + friend invite + contract renewal | send=true, p1 or p2 |
| `case_05_empty_inbox` | Completely empty inbox | send=false (silence) |
| `case_06_mixed_bulk_and_real` | Amazon shipping + HN newsletter + manager meeting request (P1) | send=true, p1=1 |

## Each case has

- `eval_case_id` — unique ID
- `prompt` — user message with mock email JSON
- `metadata.scenario_description` — for [[eval rubric]] LLM-as-judge context
- `metadata.expected_behavior` — what the rubric judges against
- `metadata.expected_silence` — boolean, used by `silence_when_unimportant` metric

## Coverage

| Dimension | Cases |
|-----------|-------|
| Pure noise (silence expected) | case_02, case_05 |
| Pure signal | case_03 |
| Mixed signal + noise | case_01, case_04, case_06 |
| Bulk sender detection | case_06 |
| Financial emails | case_01, case_04 |
| Personal emails | case_04 |
