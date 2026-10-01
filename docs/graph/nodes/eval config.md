---
aliases: ["eval config", "tests/eval/eval_config.yaml"]
tags: [eval, project/inbox-digest]
file: tests/eval/eval_config.yaml
---

# 🧪 eval config

`tests/eval/eval_config.yaml` — agents-cli eval metrics configuration.

## Metrics

| Metric | Type | What it measures |
|--------|------|-----------------|
| `custom_response_quality` | Custom (LLM-as-judge) | Filter accuracy, priority accuracy, digest quality, send gate compliance — see [[eval rubric]] |
| `agent_turn_count` | Custom (inline) | Number of ADK turns per run (should be 2: fetch + send) |
| `sent_digest` | Custom (inline) | Whether the agent sent a digest (1 = sent, 0 = skipped) |
| `silence_when_unimportant` | Custom (inline) | 1 if agent correctly stayed silent on noise-only inbox |

## Target scores

| Metric | Target |
|--------|--------|
| `custom_response_quality` | ≥ 0.8 |
| `silence_when_unimportant` | 1.0 (100%) |
| `sent_digest` | 1 for all non-silent cases |

## Run command

```bash
cd inbox-digest
agents-cli eval run
```

## Depends on

- [[eval dataset]] — 6 labelled inbox scenarios
- [[eval rubric]] — LLM-as-judge scoring function
