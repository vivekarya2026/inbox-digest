"""
WhatsApp Webhook — Inbox Digest Agent
======================================
Message +1 (555) 173-3583 on WhatsApp → get your real Gmail digest back.

Start:  bash run_webhook.sh
Setup:  uv run python setup_gmail_auth.py  (one-time Gmail auth)
"""

import asyncio
import base64
import json
import logging
import os
import re
import traceback
from contextlib import asynccontextmanager
from email import message_from_bytes

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from google.auth.transport.requests import Request as GRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("inbox-digest")

# ── Config ────────────────────────────────────────────────────────────────────
WA_TOKEN     = os.getenv("WHATSAPP_API_TOKEN", "")
PHONE_ID     = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "inbox-digest-verify-2026")
GEMINI_KEY   = os.getenv("GOOGLE_API_KEY", "")
TOKEN_FILE   = "gmail_token.json"
SCOPES       = ["https://www.googleapis.com/auth/gmail.readonly"]

# Labels / senders to always skip
SKIP_LABELS  = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS"}
SKIP_DOMAINS = {
    "noreply", "no-reply", "mailer", "newsletter", "notifications",
    "updates", "donotreply", "support", "info", "hello",
}

# ── WhatsApp sender ───────────────────────────────────────────────────────────
async def wa_send(to: str, text: str) -> None:
    async with httpx.AsyncClient() as c:
        await c.post(
            f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages",
            headers={"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"},
            json={"messaging_product": "whatsapp", "to": to, "type": "text",
                  "text": {"body": text[:4096]}},
            timeout=20,
        )

# ── Gmail helpers ─────────────────────────────────────────────────────────────
def _get_gmail_creds() -> Credentials | None:
    if not os.path.exists(TOKEN_FILE):
        return None
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GRequest())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds if creds.valid else None


def _header(headers: list, name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _should_skip(msg_data: dict) -> bool:
    headers  = msg_data["payload"].get("headers", [])
    labels   = set(msg_data.get("labelIds", []))
    sender   = _header(headers, "From").lower()
    unsubscribe = _header(headers, "List-Unsubscribe")

    if labels & SKIP_LABELS:
        return True
    if unsubscribe:
        return True
    domain = sender.split("@")[-1].split(">")[0].split(".")[0]
    if domain in SKIP_DOMAINS:
        return True
    return False


def fetch_unread_emails(max_emails: int = 20) -> list[dict]:
    """Fetch unread INBOX emails, skip noise, return clean list."""
    creds = _get_gmail_creds()
    if not creds:
        return []

    svc  = build("gmail", "v1", credentials=creds)
    res  = svc.users().messages().list(
        userId="me", labelIds=["INBOX", "UNREAD"],
        maxResults=max_emails
    ).execute()

    raw_msgs = res.get("messages", [])
    emails   = []

    for m in raw_msgs:
        try:
            data = svc.users().messages().get(
                userId="me", id=m["id"],
                format="full",
                metadataHeaders=["Subject", "From", "Date", "List-Unsubscribe"]
            ).execute()

            if _should_skip(data):
                continue

            headers = data["payload"].get("headers", [])
            subject = _header(headers, "Subject") or "(no subject)"
            sender  = _header(headers, "From")
            snippet = data.get("snippet", "")

            emails.append({
                "id":      data["id"],
                "subject": subject,
                "from":    sender,
                "snippet": snippet[:300],
            })
        except Exception as e:
            log.warning(f"Skipping message {m['id']}: {e}")

    return emails


# ── Gemini categoriser ────────────────────────────────────────────────────────
def categorize_with_gemini(emails: list[dict]) -> str:
    """Send emails to Gemini 2.5 Flash → get formatted WhatsApp digest."""
    import google.genai as genai

    client = genai.Client(api_key=GEMINI_KEY)

    email_text = "\n\n".join(
        f"Email {i+1}:\n  From: {e['from']}\n  Subject: {e['subject']}\n  Preview: {e['snippet']}"
        for i, e in enumerate(emails)
    )

    prompt = f"""You are an AI assistant that reads emails and creates a WhatsApp-ready inbox digest.

Here are {len(emails)} unread emails from the user's inbox:

{email_text}

Your task:
1. Categorize each email as P1 (urgent/action today), P2 (important/action this week), or P3 (low priority/FYI)
2. SKIP P3 emails entirely — only include P1 and P2
3. For each P1/P2 email write:
   - Priority emoji: 🔴 for P1, 🟡 for P2
   - *Subject* (bold)
   - From: sender name
   - One sentence summary
   - ➡️ Action: what to do

Use WhatsApp formatting (*bold*, _italic_).
Keep the full digest under 1500 characters.
If there are no P1/P2 emails, reply with exactly: NO_URGENT_EMAILS

Start directly with the digest, no intro text."""

    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return resp.text.strip()


# ── Main digest runner ────────────────────────────────────────────────────────
async def run_digest(sender: str) -> None:
    log.info(f"Digest triggered by {sender}")

    try:
        # 1. Check Gmail is connected
        if not os.path.exists(TOKEN_FILE):
            await wa_send(sender,
                "⚠️ Gmail isn't connected yet.\n\n"
                "Ask Vivek to run:\n`uv run python setup_gmail_auth.py`\n\n"
                "Then message again for your real digest!")
            return

        await wa_send(sender, "⏳ Checking your inbox…")

        # 2. Fetch real unread emails
        emails = fetch_unread_emails(max_emails=25)
        log.info(f"Fetched {len(emails)} emails after filtering")

        if not emails:
            await wa_send(sender,
                "📭 *Inbox Zero!*\n\nNo unread emails need your attention right now. "
                "Promotions, social, and newsletters are automatically filtered out.\n\n"
                "✅ _Check back later_")
            return

        # 3. Categorize with Gemini
        digest = categorize_with_gemini(emails)

        if digest == "NO_URGENT_EMAILS":
            await wa_send(sender,
                f"✅ *All clear!*\n\n"
                f"Checked {len(emails)} emails — nothing urgent or important right now.\n"
                f"Promotions, newsletters & social are filtered automatically.\n\n"
                f"_Reply anytime for a fresh check_ 📬")
            return

        # 4. Send the real digest
        import datetime
        ts  = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
        out = (
            f"📬 *Inbox Digest* — {ts}\n"
            f"📊 {len(emails)} emails checked\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{digest}\n\n"
            f"─────────────────\n"
            f"✅ _Reply 'digest' anytime for a fresh update_"
        )
        await wa_send(sender, out)
        log.info(f"Digest sent to {sender} ({len(out)} chars)")

    except Exception as e:
        log.error(f"Digest error: {e}\n{traceback.format_exc()}")
        await wa_send(sender, f"❌ Something went wrong: {str(e)[:150]}\nTry again in a moment.")


# ── FastAPI app ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    gmail_ok = "✅" if os.path.exists(TOKEN_FILE) else "⚠️  NOT connected (run setup_gmail_auth.py)"
    log.info(f"Webhook ready  •  Gmail: {gmail_ok}  •  PHONE_ID={PHONE_ID}")
    yield

app = FastAPI(title="Inbox Digest Webhook", lifespan=lifespan)


@app.get("/webhook")
async def verify(request: Request):
    p = dict(request.query_params)
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(status_code=403)


@app.post("/webhook")
async def receive(request: Request):
    body = await request.json()
    try:
        msgs = (
            body.get("entry", [{}])[0]
                .get("changes", [{}])[0]
                .get("value", {})
                .get("messages", [])
        )
        for msg in msgs:
            sender = msg.get("from", "")
            if sender:
                asyncio.create_task(run_digest(sender))
    except Exception as e:
        log.error(f"Parse error: {e}")
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {
        "status":    "ok",
        "gmail":     "connected" if os.path.exists(TOKEN_FILE) else "NOT_CONNECTED",
        "phone_id":  PHONE_ID,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("whatsapp_webhook:app", host="0.0.0.0", port=8081, log_level="info")
