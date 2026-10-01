# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# you may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Onboarding web app — multi-tenant self-service sign-up.

Flow:
  1. GET  /              → landing page with "Sign in with Google" button
  2. GET  /auth/login    → redirects to Google OAuth consent screen
  3. GET  /auth/callback → exchanges auth code for token; stores user; shows setup form
  4. POST /setup         → saves WhatsApp number + LLM provider/model/key; registers scheduler job
  5. GET  /dashboard     → shows user's current settings and last-run status
  6. POST /deactivate    → pauses the user's hourly job

Environment variables (set in Secret Manager / .env):
  GOOGLE_CLIENT_ID          → OAuth 2.0 web app client ID
  GOOGLE_CLIENT_SECRET      → OAuth 2.0 web app client secret
  GOOGLE_REDIRECT_URI       → e.g. https://YOUR_DOMAIN/auth/callback
  GOOGLE_CLOUD_PROJECT      → GCP project for Scheduler + Firestore
  GOOGLE_CLOUD_LOCATION     → region for Cloud Scheduler jobs
  PUBSUB_TOPIC_NAME         → topic to publish hourly trigger messages to
  SESSION_SECRET            → secret key for Starlette session middleware
  AGENT_TRIGGER_URL         → the backend's /trigger/pubsub URL (for scheduler)
  OIDC_SERVICE_ACCOUNT      → SA email that Cloud Scheduler uses for OIDC auth
"""

import json
import logging
import os
import secrets

# Import the shared user store
import sys

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.store.user_store import UserStore

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost:8081/auth/callback"
)
SESSION_SECRET = os.environ.get("SESSION_SECRET", secrets.token_hex(32))

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
OPENID_SCOPES = "openid email profile"
OAUTH_SCOPES = f"{OPENID_SCOPES} {GMAIL_SCOPE}"

GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
GCP_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
PUBSUB_TOPIC = os.environ.get("PUBSUB_TOPIC_NAME", "inbox-digest-triggers")
AGENT_TRIGGER_URL = os.environ.get("AGENT_TRIGGER_URL", "")
OIDC_SERVICE_ACCOUNT = os.environ.get("OIDC_SERVICE_ACCOUNT", "")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Inbox Digest — Onboarding")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

_static_dir = os.path.join(os.path.dirname(__file__), "static")
_templates_dir = os.path.join(os.path.dirname(__file__), "templates")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")
templates = Jinja2Templates(directory=_templates_dir)

_user_store = UserStore()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_login(request: Request) -> str | None:
    """Return user_id if logged in, else None."""
    return request.session.get("user_id")


async def _register_scheduler_job(user_id: str) -> bool:
    """Create a Cloud Scheduler job that fires hourly for this user.

    The job publishes a Pub/Sub message to PUBSUB_TOPIC with the
    subscription path set to the user_id. The backend trigger handler
    uses this as the session user_id and looks up the user config.

    Returns True on success, False on error.
    """
    if not GCP_PROJECT or not AGENT_TRIGGER_URL:
        logger.warning("GCP_PROJECT or AGENT_TRIGGER_URL not set; skipping scheduler registration")
        return False
    try:
        from google.cloud import scheduler_v1  # type: ignore[import]

        client = scheduler_v1.CloudSchedulerClient()
        parent = f"projects/{GCP_PROJECT}/locations/{GCP_LOCATION}"
        job_id = f"inbox-digest-{user_id}"
        job_name = f"{parent}/jobs/{job_id}"

        job = scheduler_v1.Job(
            name=job_name,
            schedule="0 * * * *",   # every hour
            time_zone="UTC",
            pubsub_target=scheduler_v1.PubsubTarget(
                topic_name=f"projects/{GCP_PROJECT}/topics/{PUBSUB_TOPIC}",
                data=json.dumps(
                    {
                        "subscription": f"projects/{GCP_PROJECT}/subscriptions/{user_id}",
                        "user_id": user_id,
                    }
                ).encode(),
                attributes={"user_id": user_id},
            ),
        )

        try:
            client.create_job(request={"parent": parent, "job": job})
            logger.info("Created Cloud Scheduler job: %s", job_name)
        except Exception as create_err:
            if "already exists" in str(create_err).lower():
                client.update_job(request={"job": job})
                logger.info("Updated existing Cloud Scheduler job: %s", job_name)
            else:
                raise

        return True
    except Exception as err:
        logger.error("Failed to register scheduler job for user %s: %s", user_id, err)
        return False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    user_id = _require_login(request)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "logged_in": bool(user_id), "user_id": user_id},
    )


@app.get("/auth/login")
async def auth_login(request: Request):
    """Redirect to Google OAuth consent screen."""
    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": OAUTH_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    from urllib.parse import urlencode
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(auth_url)


@app.get("/auth/callback", response_class=HTMLResponse)
async def auth_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    """Handle OAuth callback — exchange code for token, create user."""
    if error:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": f"OAuth error: {error}"},
        )

    if state != request.session.get("oauth_state"):
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "OAuth state mismatch. Please try again."},
        )

    # Exchange auth code for token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": f"Token exchange failed: {token_resp.text[:200]}"},
        )

    token_data = token_resp.json()
    gmail_token = {
        "token": token_data.get("access_token"),
        "refresh_token": token_data.get("refresh_token"),
        "token_uri": GOOGLE_TOKEN_URL,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "scopes": OAUTH_SCOPES.split(),
    }

    # Get user info
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
    userinfo = userinfo_resp.json()
    user_id = userinfo.get("sub", "")  # Google OAuth subject ID
    email = userinfo.get("email", "")

    # Store token temporarily in session for the setup form
    request.session["user_id"] = user_id
    request.session["user_email"] = email
    request.session["gmail_token"] = gmail_token

    return templates.TemplateResponse(
        "setup.html",
        {
            "request": request,
            "user_email": email,
            "providers": [
                {"value": "gemini", "label": "Google Gemini (AI Studio or Vertex AI)"},
                {"value": "openai", "label": "OpenAI (GPT-4o, GPT-4o-mini, …)"},
                {"value": "anthropic", "label": "Anthropic (Claude Sonnet, Haiku, …)"},
            ],
            "default_models": {
                "gemini": "gemini-3.8-flash",
                "openai": "gpt-4o-mini",
                "anthropic": "claude-haiku-4-20250514",
            },
        },
    )


@app.post("/setup", response_class=HTMLResponse)
async def setup(
    request: Request,
    whatsapp_number: str = Form(...),
    llm_provider: str = Form(...),
    llm_model: str = Form(...),
    llm_api_key: str = Form(...),
):
    """Save user configuration and register the hourly Cloud Scheduler job."""
    user_id = _require_login(request)
    if not user_id:
        return RedirectResponse("/auth/login", status_code=302)

    gmail_token = request.session.get("gmail_token", {})
    if not gmail_token:
        return templates.TemplateResponse(
            "error.html",
            {"request": request, "message": "Session expired. Please sign in again."},
        )

    # Validate phone number (basic E.164 check)
    whatsapp_number = whatsapp_number.strip()
    if not whatsapp_number.startswith("+") or not whatsapp_number[1:].isdigit():
        return templates.TemplateResponse(
            "setup.html",
            {
                "request": request,
                "user_email": request.session.get("user_email", ""),
                "error": "Phone number must be in E.164 format, e.g. +14155551234",
                "providers": [
                    {"value": "gemini", "label": "Google Gemini"},
                    {"value": "openai", "label": "OpenAI"},
                    {"value": "anthropic", "label": "Anthropic"},
                ],
                "default_models": {},
            },
        )

    # Save to Firestore (with KMS encryption)
    await _user_store.create_or_update_user(
        user_id=user_id,
        gmail_token_dict=gmail_token,
        whatsapp_number=whatsapp_number,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
    )

    # Register Cloud Scheduler job
    scheduler_ok = await _register_scheduler_job(user_id)

    # Clear sensitive data from session
    request.session.pop("gmail_token", None)

    return templates.TemplateResponse(
        "success.html",
        {
            "request": request,
            "user_email": request.session.get("user_email", ""),
            "whatsapp_number": whatsapp_number,
            "scheduler_registered": scheduler_ok,
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Show user's current settings and last-run status."""
    user_id = _require_login(request)
    if not user_id:
        return RedirectResponse("/auth/login", status_code=302)

    user = await _user_store.get_user(user_id)
    if not user:
        return RedirectResponse("/auth/callback", status_code=302)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user_email": request.session.get("user_email", ""),
            "whatsapp_number": user.get("whatsapp_number", ""),
            "llm_provider": user.get("llm_provider", ""),
            "llm_model": user.get("llm_model", ""),
            "last_run_at": user.get("last_run_at", "Never"),
            "active": user.get("active", True),
            "needs_reauth": user.get("needs_reauth", False),
        },
    )


@app.post("/deactivate")
async def deactivate(request: Request):
    """Pause the user's hourly job."""
    user_id = _require_login(request)
    if not user_id:
        return RedirectResponse("/auth/login", status_code=302)
    if user_id and _user_store._db is not None:
        await _user_store._db.collection("users").document(user_id).update({"active": False})
    elif user_id in _user_store._local_store:
        _user_store._local_store[user_id]["active"] = False
    return RedirectResponse("/dashboard", status_code=302)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "inbox-digest-onboarding"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8081")))
