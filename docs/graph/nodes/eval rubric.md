---
aliases: ["eval rubric", "response_quality.py", "LLM-as-judge"]
tags: [eval, project/inbox-digest]
file: tests/eval/response_quality.py
---

# ⚖️ eval rubric

`tests/eval/response_quality.py` — LLM-as-judge scoring for [[eval config]].

## Scoring dimensions (each 0.0–1.0)

| Dimension | 1.0 | 0.5 | 0.0 |
|-----------|-----|-----|-----|
| `filter_accuracy` | All social/promo correctly excluded | Minor misclassification | Major failures |
| `priority_accuracy` | P1/P2 assignments all correct | 1–2 errors | Systematic errors |
| `digest_quality` | Clear, concise, actionable | Verbose or missing action hints | Confusing/incomplete |
| `send_gate_compliance` | Sent iff P1/P2 exist | — | Sent when silent, or silent when should send |

`overall` = average of all four.

## Judge model

`gemini-3.5-flash` with `response_mime_type: "application/json"`.

## Rubric prompt

The judge receives:
1. `scenario_description` from [[eval dataset]] metadata
2. The agent's JSON response (first 3000 chars)
3. `expected_behavior` from [[eval dataset]] metadata

Returns structured JSON with scores + one-sentence reasoning.

## Used by

- [[eval config]] `custom_response_quality` metric
