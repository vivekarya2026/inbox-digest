---
aliases: ["tools/whatsapp.py", "send_whatsapp", "WhatsApp adapter"]
tags: [module/tools, layer/tool, project/inbox-digest]
file: app/tools/whatsapp.py
---

# 💬 whatsapp_tool

`send_whatsapp(to_number, message_text)` — delivers the digest via WhatsApp.

## Provider selection

Toggle with `WHATSAPP_PROVIDER` env var (default: `meta`).

| `WHATSAPP_PROVIDER` | Implementation | Credentials |
|---------------------|----------------|-------------|
| `meta` (default) | [[WhatsApp Meta API]] `graph.facebook.com/v19.0/{phone_number_id}/messages` | `WHATSAPP_API_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID` from Secret Manager |
| `twilio` | [[Twilio API]] `api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json` | `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` + `TWILIO_WHATSAPP_FROM` |

Both return the same schema: `{"status", "provider", "message_id"}`.

## [[Send Gate]]

This tool is called **only after** the hard gate in [[agent]] confirms P1+P2 count ≥ 1. The tool itself does not enforce the gate — it trusts the caller.

## Depends on

- `httpx` — HTTP client for both providers
- [[tf service]] — Secret Manager secrets are injected as env vars at deploy time

## Called by

- [[agent]] — `build_and_send_digest()` (after [[digest]])
