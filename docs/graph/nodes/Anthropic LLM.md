---
aliases: ["Anthropic", "Claude", "claude-haiku"]
tags: [external/llm, project/inbox-digest]
---

# 🤖 Anthropic LLM

Anthropic Claude — optional BYOK LLM provider via [[BYOK LiteLLM]].

## Supported models (examples)

- `claude-haiku-4-20250514` (recommended — fast, cheap)
- `claude-sonnet-4-20250514`

## Auth

User provides their own `ANTHROPIC_API_KEY` during [[onboarding_service]] setup. Key stored encrypted in [[user_store]].

## ADK integration

`LiteLlm(model="anthropic/claude-haiku-4-20250514", api_key=user_key)`

## Selected by

- [[config]] `_resolve_model()` when `llm_provider="anthropic"`
