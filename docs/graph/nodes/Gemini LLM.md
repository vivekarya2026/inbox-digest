---
aliases: ["Gemini", "Google Gemini", "gemini-3.8-flash"]
tags: [external/llm, project/inbox-digest]
---

# 🤖 Gemini LLM

Google Gemini — the default LLM provider for local dev and for users who choose `llm_provider=gemini`.

## Supported models (examples)

- `gemini-3.8-flash` (default — fast, cheap)
- `gemini-2.5-pro`

## Auth modes

| Mode | Auth | Set via |
|------|------|---------|
| AI Studio | `GOOGLE_API_KEY` | `.env` or user's BYOK key |
| Vertex AI | `GOOGLE_GENAI_USE_VERTEXAI=true` + ADC | GCP project credentials |

## ADK integration

Used directly as `Gemini(model=..., retry_options=...)` — no LiteLLM wrapper needed.

## Selected by

- [[config]] `_resolve_model()` when `llm_provider="gemini"`
- [[BYOK LiteLLM]]
