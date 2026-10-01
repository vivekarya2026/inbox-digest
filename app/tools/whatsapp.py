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

"""WhatsApp delivery tool.

Supports two providers, toggled by the WHATSAPP_PROVIDER environment
variable (default: "meta"):

  meta   → Meta WhatsApp Business Cloud API (official, free conversation
            tier, direct from Meta). Recommended for production.
  twilio → Twilio WhatsApp API (easier dev setup, per-message cost).

Both providers read their credentials from environment variables / Secret
Manager — never from user-supplied input or model context.

To swap providers, set WHATSAPP_PROVIDER=twilio and add the three
TWILIO_* env vars listed below. No code changes required.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

WHATSAPP_PROVIDER = os.environ.get("WHATSAPP_PROVIDER", "meta").lower()

# --- Meta WhatsApp Business Cloud API ---
# Set in Secret Manager / env at deploy time. Never user-supplied.
_META_API_TOKEN = os.environ.get("WHATSAPP_API_TOKEN", "")
_META_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
_META_API_VERSION = os.environ.get("WHATSAPP_API_VERSION", "v19.0")
_META_BASE_URL = f"https://graph.facebook.com/{_META_API_VERSION}"

# --- Twilio WhatsApp API (optional drop-in) ---
_TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
_TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
_TWILIO_FROM_NUMBER = os.environ.get("TWILIO_WHATSAPP_FROM", "")


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------


def _send_via_meta(to_number: str, text: str) -> dict:
    """Send a WhatsApp message via Meta Business Cloud API.

    Args:
        to_number: Recipient E.164 phone number (e.g. "+14155551234").
        text: Message body (≤4096 chars; longer messages are truncated).

    Returns:
        {"status": "sent", "message_id": "..."} or {"status": "error", ...}
    """
    if not _META_API_TOKEN or not _META_PHONE_NUMBER_ID:
        return {
            "status": "error",
            "message": (
                "WHATSAPP_API_TOKEN and WHATSAPP_PHONE_NUMBER_ID are required "
                "for the Meta provider. Set them in Secret Manager."
            ),
        }

    url = f"{_META_BASE_URL}/{_META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {_META_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number.lstrip("+"),
        "type": "text",
        "text": {"preview_url": False, "body": text[:4096]},
    }

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            logger.info("WhatsApp (Meta) sent to %s, message_id=%s", to_number, msg_id)
            return {"status": "sent", "provider": "meta", "message_id": msg_id}
        else:
            logger.error(
                "WhatsApp (Meta) send failed: %d %s", resp.status_code, resp.text[:500]
            )
            return {
                "status": "error",
                "provider": "meta",
                "http_status": resp.status_code,
                "message": resp.text[:500],
            }
    except httpx.RequestError as err:
        logger.error("WhatsApp (Meta) request error: %s", err)
        return {"status": "error", "provider": "meta", "message": str(err)}


def _send_via_twilio(to_number: str, text: str) -> dict:
    """Send a WhatsApp message via Twilio Messaging API.

    Args:
        to_number: Recipient E.164 phone number.
        text: Message body (≤1600 chars for Twilio; truncated if longer).

    Returns:
        {"status": "sent", "message_id": "..."} or {"status": "error", ...}
    """
    if not _TWILIO_ACCOUNT_SID or not _TWILIO_AUTH_TOKEN or not _TWILIO_FROM_NUMBER:
        return {
            "status": "error",
            "message": (
                "TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_WHATSAPP_FROM "
                "are required for the Twilio provider."
            ),
        }

    url = (
        f"https://api.twilio.com/2010-04-01/Accounts"
        f"/{_TWILIO_ACCOUNT_SID}/Messages.json"
    )
    data = {
        "From": f"whatsapp:{_TWILIO_FROM_NUMBER}",
        "To": f"whatsapp:{to_number}",
        "Body": text[:1600],
    }

    try:
        resp = httpx.post(
            url,
            data=data,
            auth=(_TWILIO_ACCOUNT_SID, _TWILIO_AUTH_TOKEN),
            timeout=15,
        )
        if resp.status_code in (200, 201):
            msg_sid = resp.json().get("sid", "")
            logger.info("WhatsApp (Twilio) sent to %s, sid=%s", to_number, msg_sid)
            return {"status": "sent", "provider": "twilio", "message_id": msg_sid}
        else:
            logger.error(
                "WhatsApp (Twilio) send failed: %d %s", resp.status_code, resp.text[:500]
            )
            return {
                "status": "error",
                "provider": "twilio",
                "http_status": resp.status_code,
                "message": resp.text[:500],
            }
    except httpx.RequestError as err:
        logger.error("WhatsApp (Twilio) request error: %s", err)
        return {"status": "error", "provider": "twilio", "message": str(err)}


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------


def send_whatsapp(to_number: str, message_text: str) -> dict:
    """Send a WhatsApp message to the user's registered phone number.

    This tool is the final step in a digest run. It MUST only be called
    when there is at least one P1 or P2 email to report. The agent's
    send-gate (in agent.py) enforces this; the tool itself does not.

    Args:
        to_number: Recipient phone number in E.164 format (e.g. "+14155551234").
            In the multi-tenant path this comes from the per-user config store,
            not from user input.
        message_text: The pre-formatted digest text to send.

    Returns:
        A dict with "status" ("sent" | "error"), "provider", and "message_id"
        on success, or "message" on failure.
    """
    if not to_number or not message_text:
        return {
            "status": "error",
            "message": "to_number and message_text are both required.",
        }

    if WHATSAPP_PROVIDER == "twilio":
        return _send_via_twilio(to_number, message_text)
    return _send_via_meta(to_number, message_text)
