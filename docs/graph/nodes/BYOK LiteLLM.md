---
aliases: ["BYOK", "bring your own key", "LiteLLM", "LiteLlm", "multi-provider LLM"]
tags: [concept/design, project/inbox-digest]
---

# 🔑 BYOK LiteLLM

**Bring-Your-Own-Key multi-provider LLM support.**  
Each user brings their own API key for Gemini, OpenAI, or Anthropic. The platform uses it for their runs and never touches it otherwise.

## Provider routing

```
user.llm_provider = "gemini"    → Gemini(model=..., api_key=...)
user.llm_provider = "openai"    → LiteLlm("openai/{model}", api_key=...)
user.llm_provider = "anthropic" → LiteLlm("anthropic/{model}", api_key=...)
```

ADK's `LiteLlm` wrapper makes all three look identical to the agent.

## Key isolation guarantees

| Guarantee | How enforced |
|-----------|-------------|
| Never logged | Not in any `_emit()` call in [[observability]] |
| Never in model context | Not passed to `instruction` or session history |
| Never persisted back | Not written to [[user_store]] after decryption |
| Decrypted only at runtime | [[user_store]] `get_agent_state()` → in-memory only |
| Encrypted at rest | [[Cloud KMS]] via [[user_store]] `_kms_encrypt()` |

## Supported models (examples)

| Provider | Model examples |
|----------|---------------|
| Gemini | `gemini-3.8-flash`, `gemini-2.5-pro` |
| OpenAI | `gpt-4o-mini`, `gpt-4o`, `o3-mini` |
| Anthropic | `claude-haiku-4-20250514`, `claude-sonnet-4-20250514` |

## Related

- [[config]] — `_resolve_model()`
- [[user_store]] — encrypted key storage
- [[agent]] — `root_agent = Agent(model=_resolve_model())`
