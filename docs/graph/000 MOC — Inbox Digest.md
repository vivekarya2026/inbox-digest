---
aliases: ["Inbox Digest", "inbox-digest", "agent overview"]
tags: [MOC, project/inbox-digest, index]
---

# 🗺️ Inbox Digest Agent — Map of Content

> An ambient, scheduled, multi-tenant agent. Reads Gmail hourly per user → filters noise → categorises with LLM → sends WhatsApp digest **only when P1/P2 emails exist**.

---

## ⚡ Trigger Chain

[[Cloud Scheduler]] → [[Pub Sub]] → [[fast_api_app]] → [[agent]]

---

## 🏗️ Services

| Service | Note |
|---------|------|
| ADK Agent Backend | [[agent_service]] |
| Onboarding Web App | [[onboarding_service]] |

---

## 🧩 App Modules

| Module | Role |
|--------|------|
| [[agent]] | Root ADK agent, tools wired, send gate |
| [[fast_api_app]] | Ambient FastAPI server + Pub/Sub middleware |
| [[auths]] | Gmail OAuth 2.0 config |
| [[config]] | BYOK model resolution + env defaults |
| [[digest]] | Pure-Python WhatsApp formatter |
| [[observability]] | Structured JSON logging |

### Tools
| Tool | Role |
|------|------|
| [[gmail_tool]] | `fetch_unread_emails()` + `negotiate_creds()` |
| [[whatsapp_tool]] | `send_whatsapp()` Meta / Twilio |

### Store
| Module | Role |
|--------|------|
| [[user_store]] | Firestore-backed per-user config + KMS |

---

## 🌐 External Integrations

| Integration | Note |
|-------------|------|
| Gmail API | [[Gmail API]] |
| Meta WhatsApp | [[WhatsApp Meta API]] |
| Twilio (optional) | [[Twilio API]] |
| Gemini | [[Gemini LLM]] |
| OpenAI | [[OpenAI LLM]] |
| Anthropic | [[Anthropic LLM]] |
| Google OAuth | [[Google OAuth]] |

---

## ☁️ Infrastructure

| File | Role |
|------|------|
| [[tf main]] | APIs, Firestore, KMS |
| [[tf iam]] | Service accounts + IAM roles |
| [[tf pubsub]] | Pub/Sub topic + push subscription |
| [[tf service]] | Cloud Run + Secret Manager |
| [[tf monitoring]] | Log metrics + alert policies |

---

## 🧪 Eval

| File | Role |
|------|------|
| [[eval config]] | agents-cli eval metrics config |
| [[eval dataset]] | 6 labelled inbox scenarios |
| [[eval rubric]] | LLM-as-judge: filter / priority / digest quality |

---

## 🔑 Key Design Decisions

- [[Send Gate]] — hard code rule, never LLM-bypassed
- [[Hard Filter]] — social/promo removed before LLM sees them
- [[BYOK LiteLLM]] — user's own API key, never logged
- [[OAuth Three-Stage]] — token cache → ADK exchange → consent
- [[Multi-Tenant Store]] — Firestore + KMS, one doc per user
