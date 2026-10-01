---
aliases: ["Meta WhatsApp", "WhatsApp Business Cloud API", "graph.facebook.com"]
tags: [external/api, project/inbox-digest]
---

# 💬 WhatsApp Meta API

Meta WhatsApp Business Cloud API. The default delivery channel for digests.

## Endpoint

`POST https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages`

## Message payload

```json
{
  "messaging_product": "whatsapp",
  "to": "14155551234",
  "type": "text",
  "text": { "preview_url": false, "body": "📬 Inbox Digest..." }
}
```

## Credentials

| Env var | Source |
|---------|--------|
| `WHATSAPP_API_TOKEN` | Secret Manager — operator-held |
| `WHATSAPP_PHONE_NUMBER_ID` | Secret Manager — operator-held |

Neither credential is user-supplied. Users only provide their phone number.

## Limits

- Max message length: 4096 chars (enforced by [[digest]])
- Users must have initiated a conversation with the business number first (24h window)

## Swappable

Toggle to [[Twilio API]] with `WHATSAPP_PROVIDER=twilio`. See [[whatsapp_tool]].

## Provisioned by

- [[tf service]] — Secret Manager secrets + IAM access for agent SA
