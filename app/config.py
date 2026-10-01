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

"""Centralized configuration for the Inbox Digest agent.

BYOK multi-provider model selection
────────────────────────────────────
The agent uses the user's own LLM API key, resolved at runtime from the
per-user Firestore config. The provider and model are stored as:

    llm_provider: "gemini" | "openai" | "anthropic"
    llm_model:    e.g. "gemini-3.8-flash", "gpt-4o-mini", "claude-sonnet-4-20250514"
    llm_api_key:  KMS-decrypted at runtime, never logged

In the ambient scheduler path, the caller injects these into the ADK
session state before the run starts, and the agent reads them from
tool_context.state["user_config"] (see agent.py).

In local dev / playground mode, fall back to the .env settings:
    MODEL_PROVIDER=gemini (default)
    MODEL_NAME=gemini-3.8-flash
    GOOGLE_API_KEY=... (or GOOGLE_CLOUD_PROJECT for Vertex AI)
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class DigestConfig:
    """Agent-level configuration with defaults for local dev."""

    # Default model for local dev (overridden per-user in production)
    default_provider: str = os.getenv("MODEL_PROVIDER", "gemini")
    default_model: str = os.getenv("MODEL_NAME", "gemini-3.8-flash")
    default_api_key: str = os.getenv("GOOGLE_API_KEY", "")

    # Send gate: minimum count of P1+P2 emails to trigger a digest send
    min_important_to_send: int = int(os.getenv("MIN_IMPORTANT_TO_SEND", "1"))

    # Maximum emails included in a single digest
    max_digest_items: int = int(os.getenv("MAX_DIGEST_ITEMS", "20"))


config = DigestConfig()
