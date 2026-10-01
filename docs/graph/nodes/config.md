---
aliases: ["app/config.py", "DigestConfig", "_resolve_model"]
tags: [module/app, layer/config, project/inbox-digest]
file: app/config.py
---

# ⚙️ config

`DigestConfig` dataclass + `_resolve_model()` — centralised configuration and [[BYOK LiteLLM]] model resolution.

## DigestConfig defaults

| Field | Default | Env var |
|-------|---------|---------|
| `default_provider` | `"gemini"` | `MODEL_PROVIDER` |
| `default_model` | `"gemini-3.8-flash"` | `MODEL_NAME` |
| `default_api_key` | `""` | `GOOGLE_API_KEY` |
| `min_important_to_send` | `1` | `MIN_IMPORTANT_TO_SEND` |
| `max_digest_items` | `20` | `MAX_DIGEST_ITEMS` |

## `_resolve_model(tool_context)` logic

```
1. Read provider/model/key from tool_context.state["user_config"]  ← production path
   (injected by fast_api_app from Firestore via user_store)
2. Fall back to config.default_* from .env                          ← local dev path
3. Route:
   provider="gemini"    → Gemini(model=...)
   provider="openai"    → LiteLlm("openai/{model}", api_key=...)
   provider="anthropic" → LiteLlm("anthropic/{model}", api_key=...)
```

## Security note

The `llm_api_key` is **never** written back to state, never logged, and never passed in the agent instruction. See [[BYOK LiteLLM]].

## Depends on

- `google.adk.models.Gemini`
- `google.adk.models.lite_llm.LiteLlm`

## Used by

- [[agent]] — `_resolve_model()` at module load (default) and per-run (production)
