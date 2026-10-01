# ruff: noqa
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

"""Inbox Digest agent — main entry point.

Architecture
────────────
This is an ambient, scheduled, headless agent: it is triggered by Cloud
Scheduler → Pub/Sub → ADK trigger endpoint, not by a user typing a prompt.
Each invocation represents one hourly run for one specific user.

Per-user context is injected into ADK session state before the run by the
ambient trigger handler (fast_api_app.py). The agent reads:
  - state["gmail_token"]         → Gmail OAuth credential dict (KMS-decrypted)
  - state["whatsapp_number"]     → E.164 recipient phone number
  - state["llm_provider"]        → "gemini" | "openai" | "anthropic"
  - state["llm_model"]           → e.g. "gpt-4o-mini"
  - state["llm_api_key"]         → user's API key (KMS-decrypted at trigger time)
  - state["seen_message_ids"]    → set of msg IDs already summarized (de-dup)

BYOK + LiteLLM
───────────────
The model used for categorization is resolved at import time from config
(local dev) or from tool_context.state["user_config"] at runtime (production).
ADK's LiteLlm wrapper supports Gemini / OpenAI / Anthropic with no code change.

Send gate (hard rule — not LLM judgment)
─────────────────────────────────────────
The agent MUST NOT call send_whatsapp if the count of P1+P2 emails is zero.
This is enforced in the agent instruction and as a post-processing check in
the _build_and_send tool below. Two layers of protection: LLM instruction +
deterministic code check.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import ToolContext
from google.genai import types

from app.config import config
from app.digest import format_digest
from app.tools.gmail import fetch_unread_emails
from app.tools.whatsapp import send_whatsapp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model resolution — BYOK + LiteLLM
# ---------------------------------------------------------------------------


def _resolve_model(tool_context: ToolContext | None = None):
    """Resolve the LLM model for this run.

    In the ambient (production) path:
        Reads provider/model/key from tool_context.state["user_config"].
        The key is KMS-decrypted by the trigger handler and injected into
        state. It is never logged, never passed to the model, never stored
        in session state after the run.

    In local dev:
        Falls back to config defaults from .env.

    Returns:
        An ADK-compatible model instance (Gemini or LiteLlm).
    """
    provider = config.default_provider
    model_name = config.default_model
    api_key = config.default_api_key

    if tool_context is not None:
        user_cfg = tool_context.state.get("user_config", {})
        provider = user_cfg.get("llm_provider", provider)
        model_name = user_cfg.get("llm_model", model_name)
        api_key = user_cfg.get("llm_api_key", api_key)  # KMS-decrypted by trigger handler

    if provider == "gemini":
        # Use native Gemini integration (Vertex AI or AI Studio)
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
            os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"
        return Gemini(
            model=model_name,
            retry_options=types.HttpRetryOptions(attempts=3),
        )
    elif provider == "openai":
        return LiteLlm(model=f"openai/{model_name}", api_key=api_key)
    elif provider == "anthropic":
        return LiteLlm(model=f"anthropic/{model_name}", api_key=api_key)
    else:
        # Unknown provider — fall back to default Gemini
        logger.warning("Unknown LLM provider '%s'; falling back to Gemini", provider)
        return Gemini(model=config.default_model)


# ---------------------------------------------------------------------------
# Composite tool: categorize + build digest + send
# ---------------------------------------------------------------------------

def build_and_send_digest(emails_json: str, tool_context: ToolContext) -> dict:
    """Categorize emails, build digest, and send to WhatsApp if P1/P2 exist.

    This is the second tool called by the agent (after fetch_unread_emails).
    It is separate from the LLM categorization so the agent can hand off
    the categorized list as structured JSON before calling this tool.

    The LLM calls categorize_emails_with_llm() internally to assign each
    email a category, priority, summary, and action hint.

    Args:
        emails_json: JSON string — the "emails" list from fetch_unread_emails.
        tool_context: ADK tool context for state access.

    Returns:
        A dict summarizing the run: how many sent, how many skipped, status.
    """
    try:
        emails: list[dict] = json.loads(emails_json) if isinstance(emails_json, str) else emails_json
    except json.JSONDecodeError as err:
        return {"status": "error", "message": f"Invalid emails_json: {err}"}

    if not emails:
        logger.info("No emails to process — skipping digest send")
        return {"status": "skipped", "reason": "no_unread_filtered_emails", "sent": False}

    # --- Hard gate: no send if no P1/P2 ---
    # (LLM assigns priority; this gate checks the result deterministically)
    p1_p2 = [e for e in emails if e.get("priority") in ("P1", "P2")]
    if len(p1_p2) < config.min_important_to_send:
        logger.info(
            "Digest send gate: %d P1/P2 emails found, minimum is %d — not sending",
            len(p1_p2),
            config.min_important_to_send,
        )
        return {
            "status": "skipped",
            "reason": "no_important_emails",
            "p1_count": sum(1 for e in emails if e.get("priority") == "P1"),
            "p2_count": sum(1 for e in emails if e.get("priority") == "P2"),
            "sent": False,
        }

    # Cap at max_digest_items (P1 first, then P2)
    top_items = (
        [e for e in p1_p2 if e.get("priority") == "P1"][:config.max_digest_items]
        + [e for e in p1_p2 if e.get("priority") == "P2"]
    )[:config.max_digest_items]

    # Build the digest text
    run_ts = datetime.now(tz=timezone.utc).strftime("%H:%M UTC")
    digest_text = format_digest(top_items, run_timestamp=run_ts)

    # Get the user's WhatsApp number from state
    whatsapp_number = tool_context.state.get("whatsapp_number", "")
    if not whatsapp_number:
        return {
            "status": "error",
            "message": "whatsapp_number not found in session state. User may need to re-configure.",
        }

    # Send the digest
    send_result = send_whatsapp(
        to_number=whatsapp_number,
        message_text=digest_text,
    )

    log_entry = {
        "severity": "INFO" if send_result.get("status") == "sent" else "WARNING",
        "event": "digest_sent" if send_result.get("status") == "sent" else "digest_send_failed",
        "user_id": tool_context.state.get("user_id", "unknown"),
        "p1_count": sum(1 for e in top_items if e.get("priority") == "P1"),
        "p2_count": sum(1 for e in top_items if e.get("priority") == "P2"),
        "whatsapp_status": send_result.get("status"),
        "provider": send_result.get("provider"),
    }
    import json as _json
    print(_json.dumps(log_entry), flush=True)

    return {
        "status": send_result.get("status"),
        "sent": send_result.get("status") == "sent",
        "p1_count": log_entry["p1_count"],
        "p2_count": log_entry["p2_count"],
        "whatsapp_result": send_result,
    }


# ---------------------------------------------------------------------------
# Root agent definition
# ---------------------------------------------------------------------------

_SYSTEM_INSTRUCTION = """\
You are the Inbox Digest agent. You run silently on a schedule — there is no
human watching. Your job is to:

1. Call fetch_unread_emails to get the user's filtered unread inbox emails.
   - If status is "pending_auth", stop and return {"status": "needs_reauth"}.
   - If status is "error", stop and return {"status": "error", "message": ...}.
   - If "emails" is empty, stop and return {"status": "skipped", "reason": "inbox_empty"}.

2. For each email in the returned list, assign:
   - category: one of action_needed | awaiting_reply | financial_legal |
                scheduling_calendar | informational | personal
   - priority:  P1 (urgent AND directed specifically at me) |
                P2 (important, not time-sensitive) |
                P3 (low signal, no action needed)
   - summary: one sentence (max 120 chars) explaining what the email is about
   - action:  (P1/P2 only) one short phrase describing what action is needed,
              e.g. "Reply by EOD" or "Review attached invoice"

   CATEGORIZATION RULES:
   - P1: "reply needed today", deadlines, blockers, "waiting on you", meeting
     invites for today, time-sensitive financial matters.
   - P2: follow-ups, project updates requiring a reply, upcoming deadlines
     (>24h), invoices not yet due.
   - P3: newsletters that passed the filter, digest summaries, general FYIs
     with no action needed.
   - NEVER mark a bulk marketing email P1 or P2 — if one slipped past the
     hard-filter, assign it P3.

3. Build a JSON list of ALL emails (including P3) with the fields above, then
   call build_and_send_digest with that JSON string.

4. Return the result from build_and_send_digest as your final response.

HARD RULES (not negotiable):
- Do NOT call build_and_send_digest if fetch_unread_emails returned an error or
  no emails. The tool itself also enforces the send gate.
- Do NOT add commentary, markdown, or explanation to your final response —
  return the JSON dict from build_and_send_digest directly.
- Do NOT expose the user's API key, OAuth token, or WhatsApp number in any
  output, even in error messages.
"""

root_agent = Agent(
    # Keep in sync with agents-cli-manifest.yaml
    name="inbox_digest",
    model=_resolve_model(),   # default for local dev; overridden per-user in production
    instruction=_SYSTEM_INSTRUCTION,
    tools=[fetch_unread_emails, build_and_send_digest],
)

app = App(
    root_agent=root_agent,
    name="app",
)
