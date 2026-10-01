---
aliases: ["root_agent", "app/agent.py"]
tags: [module/app, layer/agent, project/inbox-digest]
file: app/agent.py
---

# 🤖 agent

**Root ADK `Agent`** that orchestrates the hourly digest run.

## Responsibilities

- Selects the LLM model for this run via [[BYOK LiteLLM]] (`_resolve_model()`)
- Calls [[gmail_tool]] → `fetch_unread_emails()`
- Instructs the LLM to categorise and prioritise each email (P1 / P2 / P3)
- Calls `build_and_send_digest()` → internally calls [[digest]] + [[whatsapp_tool]]
- Enforces the [[Send Gate]] — never sends if P1+P2 count = 0

## Imports / depends on

- [[gmail_tool]] — `fetch_unread_emails`
- [[whatsapp_tool]] — `send_whatsapp`
- [[digest]] — `format_digest`
- [[config]] — `DigestConfig`, `_resolve_model()`
- [[observability]] — structured logging

## Called by

- [[fast_api_app]] (ambient Pub/Sub trigger path)
- `agents-cli playground` (local dev)

## Key function

```python
root_agent = Agent(
    name="inbox_digest",
    model=_resolve_model(),   # Gemini | LiteLlm("openai/...") | LiteLlm("anthropic/...")
    instruction=_SYSTEM_INSTRUCTION,
    tools=[fetch_unread_emails, build_and_send_digest],
)
```

## Related concepts

- [[BYOK LiteLLM]]
- [[Send Gate]]
- [[Categorisation Rubric]]
