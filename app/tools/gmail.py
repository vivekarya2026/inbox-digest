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

"""Gmail read tool with OAuth 2.0 credential negotiation.

Adapted from core/python/oauth-user-consent-flow/app/tools.py.
Key changes vs the Drive recipe:
  - Scope is gmail.readonly (not drive.readonly).
  - read_drive_file() replaced by fetch_unread_emails().
  - Hard-filter removes social, promotional, and bulk mail in code
    before any LLM call, keeping categorization cost low.
  - De-duplication: message IDs already seen in a prior run (stored in
    tool_context.state["seen_message_ids"]) are skipped so the same
    email never appears in two consecutive hourly digests.

negotiate_creds() is copied verbatim from the recipe — it is API-agnostic
and only the AUTH_CONFIG import changed.
"""

import base64
import json
import logging
from email.utils import parseaddr

from google.adk.tools import ToolContext
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app import auths

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hard-filter constants (no LLM cost)
# ---------------------------------------------------------------------------

# Gmail system labels that identify non-important mail.
_EXCLUDED_LABEL_IDS = frozenset(
    {
        "CATEGORY_PROMOTIONS",
        "CATEGORY_SOCIAL",
        "CATEGORY_FORUMS",
        "CATEGORY_UPDATES",  # optional — remove if users want update digests
    }
)

# Common bulk-sender domains.  Extend as needed; users can override this
# via their per-user config in a future version.
_BULK_SENDER_DOMAINS: frozenset[str] = frozenset(
    {
        "notifications.google.com",
        "mail.notion.so",
        "mail.slack.com",
        "notify.github.com",
        "noreply.github.com",
        "noreply.medium.com",
        "medium.com",
        "substack.com",
        "mailchimp.com",
        "mailgun.org",
        "sendgrid.net",
        "constantcontact.com",
        "klaviyo.com",
        "hubspot.com",
        "marketo.com",
        "salesforce.com",
        "amazon.com",
        "ebay.com",
        "paypal.com",
        "donotreply.linkedin.com",
        "linkedin.com",
        "twitter.com",
        "facebook.com",
        "instagram.com",
        "tiktok.com",
        "youtube.com",
        "accounts.google.com",
        "no-reply.accounts.google.com",
    }
)

# Maximum number of P1/P2 emails to include in a single digest.
MAX_DIGEST_ITEMS = 20


# ---------------------------------------------------------------------------
# OAuth credential negotiation (copied verbatim from oauth-user-consent-flow)
# ---------------------------------------------------------------------------


def negotiate_creds(tool_context: ToolContext) -> Credentials | dict:
    """Handle the OAuth 2.0 flow to get valid Google credentials.

    Three-stage resolution (source: oauth-user-consent-flow recipe):
    1. Check for a cached/injected token in tool_context.state.
       - In the ambient scheduler path, the Firestore token is injected
         under TOKEN_CACHE_KEY before the agent run starts.
       - Locally, the full credential dict is cached here after consent.
    2. Check for an ADK auth response (only relevant in local ADK Web UI dev).
    3. If nothing available, initiate the OAuth consent flow (local dev only).
    """
    logger.info("Negotiating Gmail credentials")

    # Stage 1: cached or injected token
    cached_token = tool_context.state.get(auths.TOKEN_CACHE_KEY)
    if cached_token is None:
        cached_token = tool_context.state.get(f"temp:{auths.TOKEN_CACHE_KEY}")

    if cached_token:
        if isinstance(cached_token, dict):
            try:
                creds = Credentials.from_authorized_user_info(
                    cached_token, list(auths.SCOPES.keys())
                )
                if creds.valid:
                    return creds
                if creds.expired and creds.refresh_token:
                    logger.debug("Refreshing expired Gmail credentials")
                    creds.refresh(Request())
                    tool_context.state[auths.TOKEN_CACHE_KEY] = json.loads(
                        creds.to_json()
                    )
                    return creds
            except Exception as err:
                logger.error("Error loading/refreshing cached credentials: %s", err)
                tool_context.state[auths.TOKEN_CACHE_KEY] = None
        elif isinstance(cached_token, str):
            return Credentials(token=cached_token)
        else:
            raise ValueError(
                f"Invalid cached token type: expected dict or str, got {type(cached_token)}"
            )

    # Stage 2: ADK auth response (local dev OAuth code exchange)
    if exchanged_creds := tool_context.get_auth_response(auths.AUTH_CONFIG):
        auth_scheme = auths.AUTH_CONFIG.auth_scheme
        auth_credential = auths.AUTH_CONFIG.raw_auth_credential
        creds = Credentials(
            token=exchanged_creds.oauth2.access_token,
            refresh_token=exchanged_creds.oauth2.refresh_token,
            token_uri=auth_scheme.flows.authorizationCode.tokenUrl,
            client_id=auth_credential.oauth2.client_id,
            client_secret=auth_credential.oauth2.client_secret,
            scopes=list(auth_scheme.flows.authorizationCode.scopes.keys()),
        )
        tool_context.state[auths.TOKEN_CACHE_KEY] = json.loads(creds.to_json())
        return creds

    # Stage 3: initiate consent (local dev only; not reached in ambient path)
    tool_context.request_credential(auths.AUTH_CONFIG)
    return {"pending": True, "message": "Awaiting Gmail authorization"}


# ---------------------------------------------------------------------------
# Hard-filter helpers
# ---------------------------------------------------------------------------


def _is_bulk_sender(from_header: str) -> bool:
    """Return True if the From address belongs to a known bulk-sender domain."""
    _, addr = parseaddr(from_header)
    domain = addr.split("@")[-1].lower() if "@" in addr else ""
    return domain in _BULK_SENDER_DOMAINS


def _get_header(headers: list[dict], name: str) -> str:
    """Extract a header value by name (case-insensitive)."""
    name_lower = name.lower()
    for h in headers:
        if h.get("name", "").lower() == name_lower:
            return h.get("value", "")
    return ""


def _extract_body_text(payload: dict) -> str:
    """Recursively extract plain-text body from a Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        try:
            return base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
        except Exception:
            return ""

    # Recurse into multipart parts
    for part in payload.get("parts", []):
        text = _extract_body_text(part)
        if text:
            return text

    return ""


def _should_exclude(msg_labels: list[str], headers: list[dict]) -> tuple[bool, str]:
    """Check hard-filter rules. Returns (should_exclude, reason)."""
    # Label-based filter
    for label in msg_labels:
        if label in _EXCLUDED_LABEL_IDS:
            return True, f"label:{label}"

    # List-Unsubscribe header (bulk sender signal)
    if _get_header(headers, "List-Unsubscribe"):
        return True, "List-Unsubscribe header present"

    # Bulk sender domain
    from_header = _get_header(headers, "From")
    if _is_bulk_sender(from_header):
        return True, f"bulk sender domain: {from_header}"

    return False, ""


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------


def fetch_unread_emails(tool_context: ToolContext) -> dict:
    """Fetch unread inbox messages, apply hard-filters, return clean list.

    This tool is the first step in every hourly digest run:
    1. Negotiate per-user OAuth credentials.
    2. Query Gmail for unread INBOX messages (up to 100 via batched get).
    3. Apply hard-filters: skip social, promo, forums, bulk senders.
    4. Skip message IDs already seen in a prior run (de-duplication).
    5. Return the filtered list for the LLM categorization step.

    De-duplication state is stored in tool_context.state["seen_message_ids"]
    and updated at the end of this call. In the ambient path the scheduler
    injects the Firestore-persisted set before the run.

    Returns:
        A dict with:
          - "emails": list of filtered email dicts
          - "total_fetched": count before filtering
          - "total_after_filter": count after filtering
          - "status": "success" | "pending_auth" | "error"
    """
    creds = negotiate_creds(tool_context)
    if isinstance(creds, dict):
        # OAuth consent pending (local dev)
        return {"status": "pending_auth", "emails": [], **creds}

    try:
        service = build("gmail", "v1", credentials=creds)

        # Fetch unread INBOX messages only
        list_resp = (
            service.users()
            .messages()
            .list(
                userId="me",
                q="is:unread in:INBOX",
                maxResults=100,
            )
            .execute()
        )
        messages = list_resp.get("messages", [])
        total_fetched = len(messages)

        if not messages:
            return {
                "status": "success",
                "emails": [],
                "total_fetched": 0,
                "total_after_filter": 0,
            }

        # De-duplication: skip IDs already processed
        seen_ids: set[str] = set(
            tool_context.state.get("seen_message_ids", [])
        )
        new_messages = [m for m in messages if m["id"] not in seen_ids]

        # Batch-fetch full message details (headers + snippet + labels)
        # Gmail batch API: up to 100 per batch
        emails: list[dict] = []
        new_seen_ids: set[str] = set()

        for msg_stub in new_messages:
            msg_id = msg_stub["id"]
            try:
                msg = (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg_id,
                        format="full",
                    )
                    .execute()
                )
            except Exception as err:
                logger.warning("Failed to fetch message %s: %s", msg_id, err)
                continue

            headers = msg.get("payload", {}).get("headers", [])
            label_ids = msg.get("labelIds", [])

            # Hard-filter check
            exclude, reason = _should_exclude(label_ids, headers)
            if exclude:
                logger.debug("Filtered out %s: %s", msg_id, reason)
                new_seen_ids.add(msg_id)  # mark so we don't re-process
                continue

            subject = _get_header(headers, "Subject") or "(no subject)"
            from_addr = _get_header(headers, "From") or ""
            date = _get_header(headers, "Date") or ""
            snippet = msg.get("snippet", "")
            body = _extract_body_text(msg.get("payload", {}))

            emails.append(
                {
                    "id": msg_id,
                    "subject": subject,
                    "from": from_addr,
                    "date": date,
                    "snippet": snippet,
                    # Limit body to first 2000 chars to keep LLM context bounded
                    "body_preview": body[:2000] if body else snippet,
                    "labels": label_ids,
                }
            )
            new_seen_ids.add(msg_id)

        # Update seen IDs in state (Firestore-persisted in the ambient path)
        # Keep a rolling window: merge new + existing, cap at 5000 IDs
        updated_seen = list(seen_ids | new_seen_ids)
        if len(updated_seen) > 5000:
            updated_seen = updated_seen[-5000:]
        tool_context.state["seen_message_ids"] = updated_seen

        logger.info(
            "Gmail fetch complete: %d fetched, %d after filter",
            total_fetched,
            len(emails),
        )
        return {
            "status": "success",
            "emails": emails,
            "total_fetched": total_fetched,
            "total_after_filter": len(emails),
        }

    except Exception as err:
        logger.error("Gmail fetch failed: %s", err)
        return {"status": "error", "message": str(err), "emails": []}
