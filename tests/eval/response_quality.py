# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

"""LLM-as-judge quality rubric for Inbox Digest eval.

Evaluates each agent response on three dimensions:
  1. filter_accuracy   — Did the agent correctly exclude social/promo mail?
  2. priority_accuracy — Were P1/P2 assignments correct and justified?
  3. digest_quality    — Is the resulting digest concise, readable, and useful?

Uses the rubric_based_final_response_quality_v1 style scoring (0.0–1.0).
Target: all three dimensions >= 0.8 before shipping.
"""

import json
import logging

logger = logging.getLogger(__name__)

RUBRIC = """
You are evaluating an AI agent that reads Gmail, categorizes emails, and sends WhatsApp digests.

The agent was given this inbox scenario:
{scenario_description}

The agent produced this response (JSON):
{agent_response}

The expected behavior was:
{expected_behavior}

Score the agent's response on three dimensions, each from 0.0 to 1.0:

1. filter_accuracy (0.0–1.0):
   - 1.0: All social/promotional/bulk emails excluded; no false negatives or positives.
   - 0.5: Minor misclassifications (e.g. one newsletter included, or one legit email excluded).
   - 0.0: Major failures (e.g. inbox full of promotions all included, or all legitimate emails excluded).

2. priority_accuracy (0.0–1.0):
   - 1.0: P1/P2 assignments are correct. Urgent emails are P1. Important non-urgent are P2. Low-signal are P3.
   - 0.5: 1–2 priority misassignments.
   - 0.0: Systematic priority errors (e.g. newsletters marked P1, or blocked-on-you emails marked P3).

3. digest_quality (0.0–1.0):
   - 1.0: Clear, concise, actionable. Each item tells you what to do and why. No fluff.
   - 0.5: Mostly clear but verbose, missing action hints, or contains irrelevant detail.
   - 0.0: Confusing, incomplete, or misleading. Missing items that were in the inbox.

Also score:
4. send_gate_compliance (0.0 or 1.0):
   - 1.0: Agent sent the digest when there were P1/P2 items; skipped when there were none.
   - 0.0: Agent sent when it should have been silent, OR was silent when there were P1/P2 items.

Return ONLY a JSON object with this structure:
{
  "filter_accuracy": <float 0.0–1.0>,
  "priority_accuracy": <float 0.0–1.0>,
  "digest_quality": <float 0.0–1.0>,
  "send_gate_compliance": <float 0.0 or 1.0>,
  "overall": <average of all four>,
  "reasoning": "<one sentence explaining the main strength or weakness>"
}
"""


def evaluate(instance: dict) -> dict:
    """LLM-as-judge evaluation function for agents-cli eval."""
    try:
        from google import genai

        client = genai.Client()
        model = "gemini-3.5-flash"

        # Extract agent response text
        agent_response_text = ""
        turns = (instance.get("agent_data") or {}).get("turns", [])
        for turn in turns:
            for part in (turn.get("response", {}) or {}).get("parts", []):
                agent_response_text += part.get("text") or ""

        # Get scenario metadata from the eval case
        metadata = instance.get("metadata", {})
        scenario_description = metadata.get("scenario_description", "No description provided.")
        expected_behavior = metadata.get("expected_behavior", "Not specified.")

        prompt = RUBRIC.format(
            scenario_description=scenario_description,
            agent_response=agent_response_text[:3000],
            expected_behavior=expected_behavior,
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        scores = json.loads(response.text)
        return {"score": scores.get("overall", 0.0), "details": scores}

    except Exception as err:
        logger.error("LLM-as-judge failed: %s", err)
        return {"score": 0.0, "details": {"error": str(err)}}
