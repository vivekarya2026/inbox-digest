"""
api/index.py — Vercel entrypoint for Inbox Digest Agent
Handles:
  GET  /              → Onboarding landing page
  GET  /auth/callback → Gmail OAuth callback (saves token to Appwrite)
  GET  /webhook       → Meta webhook verification
  POST /webhook       → Incoming WhatsApp messages → trigger digest
  GET  /health        → Health check
"""

import asyncio
import json
import logging
import os
import traceback
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

# Appwrite SDK
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("inbox-digest")

# ── Env config ────────────────────────────────────────────────────────────────
WA_TOKEN     = os.environ.get("WHATSAPP_API_TOKEN", "")
PHONE_ID     = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "inbox-digest-verify-2026")
GEMINI_KEY   = os.environ.get("GOOGLE_API_KEY", "")
VERCEL_URL   = os.environ.get("VERCEL_URL", "")  # auto-set by Vercel
APP_URL      = os.environ.get("APP_URL", f"https://{VERCEL_URL}" if VERCEL_URL else "")

# Gmail OAuth
GMAIL_CLIENT_ID     = os.environ.get("OAUTH_CLIENT_ID", "")
GMAIL_CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "")
GMAIL_SCOPES        = ["https://www.googleapis.com/auth/gmail.readonly"]

# Appwrite
AW_ENDPOINT   = os.environ.get("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
AW_PROJECT_ID = os.environ.get("APPWRITE_PROJECT_ID", "")
AW_API_KEY    = os.environ.get("APPWRITE_API_KEY", "")
AW_DB_ID      = os.environ.get("APPWRITE_DATABASE_ID", "inbox-digest-db")
AW_COL_USERS  = "users"

# Noise filters
SKIP_LABELS  = {"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL", "CATEGORY_FORUMS"}
SKIP_DOMAINS = {"noreply","no-reply","mailer","newsletter","notifications",
                "updates","donotreply","support","info","hello"}

# ── Appwrite helpers ──────────────────────────────────────────────────────────
def _appwrite_client() -> Client:
    c = Client()
    c.set_endpoint(AW_ENDPOINT)
    c.set_project(AW_PROJECT_ID)
    c.set_key(AW_API_KEY)
    return c

def _get_user(email: str) -> dict | None:
    try:
        db  = Databases(_appwrite_client())
        res = db.list_documents(AW_DB_ID, AW_COL_USERS,
                                queries=[f'equal("email", "{email}")'])
        docs = res.get("documents", [])
        return docs[0] if docs else None
    except Exception as e:
        log.error(f"Appwrite get_user error: {e}")
        return None

def _save_token(email: str, token_json: str, wa_number: str = "") -> None:
    try:
        db  = Databases(_appwrite_client())
        existing = _get_user(email)
        data = {
            "email":        email,
            "gmail_token":  token_json,
            "wa_number":    wa_number,
            "updated_at":   datetime.now(timezone.utc).isoformat(),
        }
        if existing:
            db.update_document(AW_DB_ID, AW_COL_USERS, existing["$id"], data)
        else:
            db.create_document(AW_DB_ID, AW_COL_USERS, ID.unique(), data)
        log.info(f"Token saved for {email}")
    except Exception as e:
        log.error(f"Appwrite save_token error: {e}")

def _get_token_for_number(wa_number: str) -> str | None:
    """Find Gmail token for a WhatsApp number."""
    try:
        db  = Databases(_appwrite_client())
        res = db.list_documents(AW_DB_ID, AW_COL_USERS,
                                queries=[f'equal("wa_number", "{wa_number}")'])
        docs = res.get("documents", [])
        return docs[0].get("gmail_token") if docs else None
    except Exception as e:
        log.error(f"Appwrite get_token error: {e}")
        return None

# ── Gmail helpers ─────────────────────────────────────────────────────────────
def _build_creds(token_json: str) -> Credentials:
    from google.auth.transport.requests import Request as GReq
    creds = Credentials.from_authorized_user_info(
        json.loads(token_json), GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GReq())
    return creds

def _header(headers: list, name: str) -> str:
    return next((h["value"] for h in headers
                 if h["name"].lower() == name.lower()), "")

def _should_skip(msg_data: dict) -> bool:
    headers = msg_data["payload"].get("headers", [])
    labels  = set(msg_data.get("labelIds", []))
    sender  = _header(headers, "From").lower()
    if labels & SKIP_LABELS:           return True
    if _header(headers, "List-Unsubscribe"): return True
    domain = sender.split("@")[-1].split(">")[0].split(".")[0]
    return domain in SKIP_DOMAINS

def fetch_emails(token_json: str, max_results: int = 25) -> list[dict]:
    from googleapiclient.discovery import build
    creds = _build_creds(token_json)
    svc   = build("gmail", "v1", credentials=creds)
    res   = svc.users().messages().list(
        userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results
    ).execute()
    emails = []
    for m in res.get("messages", []):
        try:
            data = svc.users().messages().get(
                userId="me", id=m["id"], format="full",
                metadataHeaders=["Subject","From","Date","List-Unsubscribe"]
            ).execute()
            if _should_skip(data): continue
            hdrs = data["payload"].get("headers", [])
            emails.append({
                "id":      data["id"],
                "subject": _header(hdrs, "Subject") or "(no subject)",
                "from":    _header(hdrs, "From"),
                "snippet": data.get("snippet", "")[:300],
            })
        except Exception as e:
            log.warning(f"Skip msg {m['id']}: {e}")
    return emails

# ── Gemini categoriser ────────────────────────────────────────────────────────
def categorize(emails: list[dict]) -> str:
    import google.genai as genai
    client = genai.Client(api_key=GEMINI_KEY)
    email_text = "\n\n".join(
        f"Email {i+1}:\n  From: {e['from']}\n  Subject: {e['subject']}\n  Preview: {e['snippet']}"
        for i, e in enumerate(emails)
    )
    prompt = (
        f"You are an AI assistant creating a WhatsApp inbox digest.\n"
        f"Here are {len(emails)} unread emails:\n\n{email_text}\n\n"
        "Categorize each as P1 (urgent), P2 (important this week), or P3 (low).\n"
        "ONLY include P1 and P2 emails. For each write:\n"
        "🔴 *Subject* (P1) or 🟡 *Subject* (P2)\n"
        "From: sender\nSummary: one sentence\n➡️ Action: what to do\n\n"
        "Use WhatsApp *bold* and _italic_. Max 1400 chars.\n"
        "If no P1/P2 emails exist, reply exactly: NO_URGENT_EMAILS"
    )
    resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return resp.text.strip()

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

# ── Digest runner ─────────────────────────────────────────────────────────────
async def run_digest(sender: str) -> None:
    log.info(f"Digest triggered by {sender}")
    try:
        token_json = _get_token_for_number(sender)
        if not token_json:
            await wa_send(sender,
                f"👋 Hi! I'm your *Inbox Digest* assistant.\n\n"
                f"To get started, connect your Gmail:\n"
                f"👉 {APP_URL}/connect?wa={sender}\n\n"
                f"Takes 30 seconds — then reply here for your real email digest!")
            return

        await wa_send(sender, "⏳ Fetching your inbox…")
        emails = fetch_emails(token_json)
        if not emails:
            await wa_send(sender, "📭 *Inbox Zero!* No unread emails need attention right now.")
            return

        digest = categorize(emails)
        if digest == "NO_URGENT_EMAILS":
            await wa_send(sender,
                f"✅ *All clear!* Checked {len(emails)} emails — nothing urgent right now.")
            return

        ts  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        out = (f"📬 *Inbox Digest* — {ts}\n"
               f"📊 {len(emails)} emails checked · AI-filtered\n"
               f"━━━━━━━━━━━━━━━━━━━━━\n\n"
               f"{digest}\n\n"
               f"─────────────────\n"
               f"✅ _Reply anytime for a fresh digest_")
        await wa_send(sender, out)
        log.info(f"Digest delivered to {sender}")

    except Exception as e:
        log.error(f"Digest error: {e}\n{traceback.format_exc()}")
        await wa_send(sender, f"❌ Error: {str(e)[:150]}\nPlease try again.")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Inbox Digest")

@app.get("/", response_class=HTMLResponse)
async def landing():
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Inbox Digest — AI Email Summary on WhatsApp</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0f0f0f; color: #f0f0f0; min-height: 100vh;
           display: flex; align-items: center; justify-content: center; }
    .card { max-width: 480px; width: 90%; text-align: center; padding: 48px 32px; }
    .icon { font-size: 56px; margin-bottom: 24px; }
    h1 { font-size: 2rem; font-weight: 700; margin-bottom: 12px; }
    p { color: #888; font-size: 1.05rem; line-height: 1.6; margin-bottom: 32px; }
    .btn { display: inline-block; background: #25D366; color: white;
           padding: 14px 32px; border-radius: 50px; font-size: 1rem;
           font-weight: 600; text-decoration: none; }
    .steps { text-align: left; margin-top: 40px; border-top: 1px solid #222; padding-top: 32px; }
    .step { display: flex; gap: 16px; margin-bottom: 20px; align-items: flex-start; }
    .num { background: #25D366; color: white; width: 28px; height: 28px;
           border-radius: 50%; display: flex; align-items: center; justify-content: center;
           font-weight: 700; flex-shrink: 0; }
    .step p { color: #ccc; margin: 0; font-size: 0.95rem; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">📬</div>
    <h1>Inbox Digest</h1>
    <p>Your Gmail inbox — summarized, prioritized, and delivered to WhatsApp every hour by Gemini AI.</p>
    <a href="/connect" class="btn">Connect Gmail → WhatsApp</a>
    <div class="steps">
      <div class="step"><div class="num">1</div><p>Sign in with Google — read-only Gmail access</p></div>
      <div class="step"><div class="num">2</div><p>Enter your WhatsApp number</p></div>
      <div class="step"><div class="num">3</div><p>Message the bot anytime for your digest</p></div>
    </div>
  </div>
</body>
</html>"""

@app.get("/connect", response_class=HTMLResponse)
async def connect_page(wa: str = ""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Connect Gmail — Inbox Digest</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, sans-serif; background: #0f0f0f; color: #f0f0f0;
            min-height: 100vh; display: flex; align-items: center; justify-content: center; }}
    .card {{ max-width: 420px; width: 90%; padding: 40px 32px; }}
    h2 {{ font-size: 1.5rem; margin-bottom: 8px; }}
    p {{ color: #888; margin-bottom: 28px; line-height: 1.5; }}
    label {{ font-size: 0.85rem; color: #aaa; display: block; margin-bottom: 6px; }}
    input {{ width: 100%; background: #1a1a1a; border: 1px solid #333; color: white;
             padding: 12px 16px; border-radius: 10px; font-size: 1rem; margin-bottom: 20px; }}
    .btn {{ width: 100%; background: #4285f4; color: white; padding: 14px;
            border-radius: 10px; font-size: 1rem; font-weight: 600;
            border: none; cursor: pointer; display: flex; align-items: center;
            justify-content: center; gap: 10px; }}
    .btn:hover {{ background: #3574e2; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>📬 Connect Your Gmail</h2>
    <p>We'll read your inbox (read-only) and send a WhatsApp digest when important emails arrive.</p>
    <form action="/auth/start" method="get">
      <label>WhatsApp Number (with country code)</label>
      <input type="tel" name="wa" placeholder="+1 630 284 3308" value="{wa}" required>
      <button type="submit" class="btn">
        <svg width="20" height="20" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20H24v8h11.3C33.7 33.2 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3 0 5.7 1.1 7.8 2.9l6-6C34.4 6.5 29.5 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-4z"/><path fill="#FF3D00" d="M6.3 14.7l7 5.1C15 16.1 19.2 13 24 13c3 0 5.7 1.1 7.8 2.9l6-6C34.4 6.5 29.5 4 24 4 16.3 4 9.7 8.4 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-1.9 13.5-5L31 33.7C29.1 35.1 26.6 36 24 36c-5.2 0-9.6-2.8-11.2-7l-7 5.4C9.6 39.5 16.3 44 24 44z"/><path fill="#1976D2" d="M43.6 20H24v8h11.3c-.9 2.4-2.5 4.4-4.5 5.8l6.5 5C41.2 35.4 44 30.1 44 24c0-1.3-.1-2.7-.4-4z"/></svg>
        Sign in with Google
      </button>
    </form>
  </div>
</body>
</html>"""

@app.get("/auth/start")
async def auth_start(wa: str):
    """Begin Gmail OAuth flow — redirect to Google."""
    callback_url = f"{APP_URL}/auth/callback"
    flow = Flow.from_client_config(
        {"web": {
            "client_id":     GMAIL_CLIENT_ID,
            "client_secret": GMAIL_CLIENT_SECRET,
            "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
            "token_uri":     "https://oauth2.googleapis.com/token",
            "redirect_uris": [callback_url],
        }},
        scopes=GMAIL_SCOPES,
        redirect_uri=callback_url,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=wa,          # pass WhatsApp number through state
    )
    return RedirectResponse(auth_url)

@app.get("/auth/callback")
async def auth_callback(code: str, state: str = ""):
    """Gmail OAuth callback — saves token to Appwrite."""
    wa_number = state
    callback_url = f"{APP_URL}/auth/callback"
    try:
        flow = Flow.from_client_config(
            {"web": {
                "client_id":     GMAIL_CLIENT_ID,
                "client_secret": GMAIL_CLIENT_SECRET,
                "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
                "token_uri":     "https://oauth2.googleapis.com/token",
                "redirect_uris": [callback_url],
            }},
            scopes=GMAIL_SCOPES,
            redirect_uri=callback_url,
        )
        flow.fetch_token(code=code)
        creds = flow.credentials

        # Get Gmail email address
        import google.auth.transport.requests as gtreq
        from googleapiclient.discovery import build
        svc    = build("oauth2", "v2", credentials=creds)
        info   = svc.userinfo().get().execute()
        email  = info.get("email", "unknown")

        # Normalize WhatsApp number
        wa_clean = wa_number.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")

        # Save to Appwrite
        _save_token(email, creds.to_json(), wa_clean)

        return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Connected! — Inbox Digest</title>
<style>body{{font-family:-apple-system,sans-serif;background:#0f0f0f;color:#f0f0f0;
min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center}}
.card{{max-width:400px;width:90%;padding:48px 32px}}.icon{{font-size:64px;margin-bottom:24px}}
h2{{font-size:1.8rem;margin-bottom:12px}}p{{color:#888;line-height:1.6;margin-bottom:8px}}
.wa{{background:#25D366;color:white;padding:12px 24px;border-radius:50px;
display:inline-block;margin-top:24px;font-weight:600}}</style></head>
<body><div class="card">
  <div class="icon">🎉</div>
  <h2>You're connected!</h2>
  <p>Gmail: <strong>{email}</strong></p>
  <p>WhatsApp: <strong>+{wa_clean}</strong></p>
  <p style="margin-top:20px">Now message the bot on WhatsApp to get your first digest!</p>
  <div class="wa">Message +1 (555) 173-3583</div>
</div></body></html>""")

    except Exception as e:
        log.error(f"OAuth callback error: {e}\n{traceback.format_exc()}")
        return HTMLResponse(f"<h1>Error: {e}</h1>", status_code=500)

# ── WhatsApp webhook ──────────────────────────────────────────────────────────
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
        msgs = (body.get("entry", [{}])[0]
                    .get("changes", [{}])[0]
                    .get("value", {})
                    .get("messages", []))
        for msg in msgs:
            sender = msg.get("from", "")
            if sender:
                asyncio.create_task(run_digest(sender))
    except Exception as e:
        log.error(f"Webhook parse error: {e}")
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0",
            "appwrite": bool(AW_PROJECT_ID), "app_url": APP_URL}
