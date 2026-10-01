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

"""FastAPI entry point for the ambient Inbox Digest agent backend.

Configures the ADK server with Pub/Sub trigger endpoints so the agent
runs headlessly when Cloud Scheduler publishes a per-user job message.

Middleware (run before the ADK trigger handler):
  1. Normalize Pub/Sub subscription paths to short names (user_id).
  2. Inject per-user config from Firestore into the trigger payload's
     session state so the agent can access Gmail tokens, WhatsApp number,
     and LLM credentials without the trigger message carrying secrets.

Per-user state injected into session state before each run:
  - gmail_token        → decrypted OAuth credential dict
  - whatsapp_number    → E.164 phone number
  - llm_provider       → "gemini" | "openai" | "anthropic"
  - llm_model          → model name string
  - llm_api_key        → KMS-decrypted API key (in-memory only, not persisted)
  - seen_message_ids   → rolling set of already-summarized Gmail message IDs
  - user_id            → Firestore document ID (Google OAuth sub)
"""

import json
import logging
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from google.adk.cli.fast_api import get_fast_api_app

from app.store.user_store import UserStore

load_dotenv()
logger = logging.getLogger(__name__)

AGENTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Initialize the user store (Firestore-backed in production, in-memory stub for local dev)
_user_store = UserStore()

# ---------------------------------------------------------------------------
# ADK ambient app (Pub/Sub trigger enabled, no web UI)
# ---------------------------------------------------------------------------

app: FastAPI = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    web=False,
    trigger_sources=["pubsub"],
)


# ---------------------------------------------------------------------------
# Middleware 1: normalize Pub/Sub subscription path → short user_id
# ---------------------------------------------------------------------------


@app.middleware("http")
async def normalize_pubsub_and_inject_user_state(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Normalize subscription name and inject per-user state before trigger handling.

    Pub/Sub push deliveries use the fully-qualified subscription path
    (projects/PROJECT/subscriptions/NAME) as the session user_id.
    We normalize to NAME (which is the Google OAuth sub / user_id) and then
    inject the user's runtime config from Firestore into the request body's
    initialState so the ADK runner has all the context it needs.
    """
    if (
        request.url.path.endswith("/trigger/pubsub")
        and request.method == "POST"
    ):
        body = await request.body()
        try:
            data = json.loads(body)
            sub = data.get("subscription", "")

            # Normalize fully-qualified subscription path → short name (= user_id)
            if "/" in sub:
                user_id = sub.rsplit("/", 1)[-1]
                data["subscription"] = user_id
            else:
                user_id = sub

            # Inject per-user runtime state from Firestore
            user_state = await _user_store.get_agent_state(user_id)
            if user_state:
                # Merge into existing initialState if present
                existing_state = data.get("initialState", {})
                data["initialState"] = {**existing_state, **user_state}
                logger.info("Injected state for user %s into trigger payload", user_id)
            else:
                logger.warning(
                    "No user config found for user_id=%s; run will likely fail auth",
                    user_id,
                )

            request._body = json.dumps(data).encode()

        except (json.JSONDecodeError, KeyError) as err:
            logger.warning("Failed to process trigger payload: %s", err)

    return await call_next(request)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "inbox-digest-agent"}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
