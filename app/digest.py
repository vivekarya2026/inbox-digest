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

"""Pure-Python digest formatter.

Converts the LLM-categorized email list into a WhatsApp-friendly text
message. No LLM call needed here — it's a deterministic template render.

WhatsApp text limits:
  - Max message length: 4096 chars (Meta Cloud API)
  - No markdown rendering: use plain text + emojis for structure
"""

from __future__ import annotations

from datetime import UTC, datetime

# Priority emoji markers for scan-ability
_PRIORITY_EMOJI = {
    "P1": "🔴",
    "P2": "🟡",
    "P3": "🟢",
}

_CATEGORY_EMOJI = {
    "action_needed": "✅",
    "awaiting_reply": "💬",
    "financial_legal": "💰",
    "scheduling_calendar": "📅",
    "informational": "ℹ️",  # noqa: RUF001 — intentional info emoji for WhatsApp
    "personal": "👤",
}

MAX_SUBJECT_LEN = 60
MAX_SENDER_LEN = 30


def format_digest(emails: list[dict], run_timestamp: str | None = None) -> str:
    """Format a list of categorized emails into a WhatsApp digest message.

    Only includes P1 and P2 items (the caller must pre-filter to P1/P2
    before calling this function — the agent's send-gate handles that).

    Args:
        emails: List of email dicts, each with:
            - "subject": str
            - "from": str
            - "priority": "P1" | "P2" | "P3"
            - "category": one of the category constants
            - "summary": short 1-line LLM summary
            - "action": optional 1-line action hint (from LLM)
        run_timestamp: ISO timestamp string for the digest header.

    Returns:
        Formatted WhatsApp message string (≤4096 chars).
    """
    now_str = run_timestamp or datetime.now(tz=UTC).strftime("%H:%M UTC")

    p1_items = [e for e in emails if e.get("priority") == "P1"]
    p2_items = [e for e in emails if e.get("priority") == "P2"]

    lines: list[str] = []
    lines.append(f"📬 *Inbox Digest* — {now_str}")
    lines.append(f"📊 {len(p1_items)} urgent · {len(p2_items)} important")
    lines.append("")

    def _render_item(email: dict, index: int) -> list[str]:
        priority = email.get("priority", "P2")
        category = email.get("category", "informational")
        priority_icon = _PRIORITY_EMOJI.get(priority, "🟡")
        category_icon = _CATEGORY_EMOJI.get(category, "ℹ️")  # noqa: RUF001

        subject = email.get("subject", "(no subject)")
        if len(subject) > MAX_SUBJECT_LEN:
            subject = subject[:MAX_SUBJECT_LEN] + "…"

        sender = email.get("from", "")
        # Strip angle-bracket address, keep display name if present
        if "<" in sender:
            sender = sender.split("<")[0].strip().strip('"')
        if len(sender) > MAX_SENDER_LEN:
            sender = sender[:MAX_SENDER_LEN] + "…"

        summary = email.get("summary", "")
        action = email.get("action", "")

        item_lines = [
            f"{priority_icon} {index}. {subject}",
            f"   {category_icon} From: {sender}",
        ]
        if summary:
            item_lines.append(f"   {summary}")
        if action:
            item_lines.append(f"   ➡️ {action}")
        return item_lines

    # P1 section
    if p1_items:
        lines.append("━━━ 🔴 URGENT ━━━")
        for i, email in enumerate(p1_items, start=1):
            lines.extend(_render_item(email, i))
            lines.append("")

    # P2 section
    if p2_items:
        lines.append("━━━ 🟡 IMPORTANT ━━━")
        for i, email in enumerate(p2_items, start=len(p1_items) + 1):
            lines.extend(_render_item(email, i))
            lines.append("")

    total = len(p1_items) + len(p2_items)
    lines.append("─────────────────")
    lines.append(f"📥 {total} email(s) need your attention.")

    full_text = "\n".join(lines)

    # Truncate gracefully if over WhatsApp limit
    if len(full_text) > 4000:
        full_text = full_text[:3980] + "\n\n… (digest truncated)"

    return full_text
