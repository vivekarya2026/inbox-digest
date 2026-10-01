---
aliases: ["OpenAI", "GPT", "gpt-4o-mini"]
tags: [external/llm, project/inbox-digest]
---

# 🤖 OpenAI LLM

OpenAI — optional BYOK LLM provider via [[BYOK LiteLLM]].

## Supported models (examples)

- `gpt-4o-mini` (recommended — fast, cheap)
- `gpt-4o`
- `o3-mini`

## Auth

User provides their own `OPENAI_API_KEY` during [[onboarding_service]] setup. Key stored encrypted in [[user_store]].

## ADK integration

`LiteLlm(model="openai/gpt-4o-mini", api_key=user_key)`

## Selected by

- [[config]] `_resolve_model()` when `llm_provider="openai"`
