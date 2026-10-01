---
aliases: ["Twilio WhatsApp", "api.twilio.com"]
tags: [external/api, project/inbox-digest]
---

# 💬 Twilio API

Optional drop-in WhatsApp provider. Activated by setting `WHATSAPP_PROVIDER=twilio`.

## Endpoint

`POST https://api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json`

## Credentials

| Env var | Description |
|---------|-------------|
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token (HTTP basic auth) |
| `TWILIO_WHATSAPP_FROM` | Twilio WhatsApp sandbox or approved number |

## Compared to [[WhatsApp Meta API]]

| | Meta | Twilio |
|--|------|--------|
| Setup complexity | Higher (Meta Business approval) | Lower (sandbox in minutes) |
| Cost | Free conversation tier | Per-message fee |
| Reliability | Direct to Meta infra | Via Twilio relay |

## Swapping providers

No code change needed. The [[whatsapp_tool]] picks the provider with a single `if WHATSAPP_PROVIDER == "twilio"` branch.

## Used by

- [[whatsapp_tool]] — `_send_via_twilio()`
