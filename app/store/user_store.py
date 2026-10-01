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

"""Per-user config store — Firestore-backed with KMS encryption.

Stores one Firestore document per user under the "users" collection:

  /users/{user_id}
    gmail_token_encrypted: bytes    — KMS-encrypted OAuth credential dict
    whatsapp_number: str            — E.164 phone number
    llm_provider: str               — "gemini" | "openai" | "anthropic"
    llm_model: str                  — e.g. "gpt-4o-mini"
    llm_api_key_encrypted: bytes    — KMS-encrypted LLM API key
    seen_message_ids: list[str]     — rolling de-dup window (max 5000)
    last_run_at: str                — ISO 8601 timestamp
    active: bool                    — false = paused/deactivated
    needs_reauth: bool              — true = Gmail consent was revoked

KMS encryption
───────────────
Uses Google Cloud KMS symmetric encryption. The key name is read from
GOOGLE_KMS_KEY_NAME env var:
  projects/PROJECT/locations/global/keyRings/RING/cryptoKeys/KEY

If KMS is not configured (local dev), the store falls back to base64
encoding as a no-op placeholder. Set KMS_ENABLED=false to disable KMS.
"""

import base64
import json
import logging
import os

logger = logging.getLogger(__name__)

KMS_ENABLED = os.environ.get("KMS_ENABLED", "true").lower() == "true"
KMS_KEY_NAME = os.environ.get("GOOGLE_KMS_KEY_NAME", "")
FIRESTORE_COLLECTION = os.environ.get("FIRESTORE_COLLECTION", "users")

# ---------------------------------------------------------------------------
# KMS helpers
# ---------------------------------------------------------------------------


def _kms_encrypt(plaintext: str) -> bytes:
    """Encrypt a string using Cloud KMS. Falls back to base64 if KMS disabled."""
    if not KMS_ENABLED or not KMS_KEY_NAME:
        return base64.b64encode(plaintext.encode())
    try:
        from google.cloud import kms  # type: ignore[import]

        client = kms.KeyManagementServiceClient()
        response = client.encrypt(
            request={
                "name": KMS_KEY_NAME,
                "plaintext": plaintext.encode(),
            }
        )
        return response.ciphertext
    except Exception as err:
        logger.error("KMS encrypt failed, falling back to base64: %s", err)
        return base64.b64encode(plaintext.encode())


def _kms_decrypt(ciphertext: bytes) -> str:
    """Decrypt bytes using Cloud KMS. Falls back to base64 if KMS disabled."""
    if not KMS_ENABLED or not KMS_KEY_NAME:
        return base64.b64decode(ciphertext).decode()
    try:
        from google.cloud import kms  # type: ignore[import]

        client = kms.KeyManagementServiceClient()
        response = client.decrypt(
            request={
                "name": KMS_KEY_NAME,
                "ciphertext": ciphertext,
            }
        )
        return response.plaintext.decode()
    except Exception as err:
        logger.error("KMS decrypt failed, attempting base64 fallback: %s", err)
        try:
            return base64.b64decode(ciphertext).decode()
        except Exception:
            raise RuntimeError(f"KMS decrypt failed and base64 fallback failed: {err}") from err


# ---------------------------------------------------------------------------
# UserStore
# ---------------------------------------------------------------------------


class UserStore:
    """Firestore-backed per-user config store.

    Falls back to an in-memory dict in local dev when Firestore is not
    available (FIRESTORE_ENABLED=false or google-cloud-firestore not installed).
    """

    def __init__(self) -> None:
        self._firestore_enabled = os.environ.get("FIRESTORE_ENABLED", "true").lower() == "true"
        self._db = None
        self._local_store: dict[str, dict] = {}  # in-memory fallback

        if self._firestore_enabled:
            try:
                from google.cloud import firestore  # type: ignore[import]

                project = os.environ.get("GOOGLE_CLOUD_PROJECT")
                self._db = firestore.AsyncClient(project=project)
                logger.info("Firestore client initialized (project=%s)", project)
            except Exception as err:
                logger.warning("Firestore unavailable, using in-memory store: %s", err)
                self._firestore_enabled = False

    # -------------------------------------------------------------------------
    # Write operations
    # -------------------------------------------------------------------------

    async def create_or_update_user(
        self,
        user_id: str,
        gmail_token_dict: dict,
        whatsapp_number: str,
        llm_provider: str,
        llm_model: str,
        llm_api_key: str,
    ) -> None:
        """Create or update a user's configuration.

        Encrypts OAuth token and LLM API key before writing to Firestore.
        """
        gmail_token_enc = _kms_encrypt(json.dumps(gmail_token_dict))
        api_key_enc = _kms_encrypt(llm_api_key)

        doc = {
            "gmail_token_encrypted": gmail_token_enc,
            "whatsapp_number": whatsapp_number,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "llm_api_key_encrypted": api_key_enc,
            "seen_message_ids": [],
            "active": True,
            "needs_reauth": False,
        }

        if self._db is not None:
            await self._db.collection(FIRESTORE_COLLECTION).document(user_id).set(
                doc, merge=True
            )
        else:
            self._local_store[user_id] = doc

        logger.info("User config written for user_id=%s", user_id)

    async def update_seen_ids(self, user_id: str, seen_ids: list[str]) -> None:
        """Persist the updated seen_message_ids for a user after a run."""
        if self._db is not None:
            from google.cloud import firestore  # type: ignore[import]

            await self._db.collection(FIRESTORE_COLLECTION).document(user_id).update(
                {
                    "seen_message_ids": seen_ids[-5000:],  # rolling window
                    "last_run_at": firestore.SERVER_TIMESTAMP,
                }
            )
        elif user_id in self._local_store:
            self._local_store[user_id]["seen_message_ids"] = seen_ids[-5000:]

    async def mark_needs_reauth(self, user_id: str) -> None:
        """Flag a user as needing to re-authenticate Gmail."""
        if self._db is not None:
            await self._db.collection(FIRESTORE_COLLECTION).document(user_id).update(
                {"needs_reauth": True}
            )
        elif user_id in self._local_store:
            self._local_store[user_id]["needs_reauth"] = True

    # -------------------------------------------------------------------------
    # Read operations
    # -------------------------------------------------------------------------

    async def get_user(self, user_id: str) -> dict | None:
        """Return the raw Firestore document for a user, or None if not found."""
        if self._db is not None:
            doc = await self._db.collection(FIRESTORE_COLLECTION).document(user_id).get()
            return doc.to_dict() if doc.exists else None
        return self._local_store.get(user_id)

    async def get_agent_state(self, user_id: str) -> dict | None:
        """Return the per-user state dict to inject into the ADK session.

        Decrypts the Gmail token and LLM API key. Returns None if the user
        is not found, inactive, or needs re-authentication.

        The returned dict is merged into tool_context.state by the middleware
        in fast_api_app.py. The llm_api_key is in-memory only — it is never
        written back to Firestore or logged.
        """
        user = await self.get_user(user_id)
        if user is None:
            logger.warning("get_agent_state: user_id=%s not found", user_id)
            return None
        if not user.get("active", True):
            logger.info("get_agent_state: user_id=%s is inactive — skipping run", user_id)
            return None
        if user.get("needs_reauth", False):
            logger.warning(
                "get_agent_state: user_id=%s needs re-auth — skipping run", user_id
            )
            return None

        try:
            gmail_token = json.loads(
                _kms_decrypt(user["gmail_token_encrypted"])
            )
            llm_api_key = _kms_decrypt(user["llm_api_key_encrypted"])
        except Exception as err:
            logger.error("Failed to decrypt secrets for user_id=%s: %s", user_id, err)
            return None

        return {
            "user_id": user_id,
            "gmail_token": gmail_token,          # injected as TOKEN_CACHE_KEY in auths.py
            "whatsapp_number": user.get("whatsapp_number", ""),
            "user_config": {
                "llm_provider": user.get("llm_provider", "gemini"),
                "llm_model": user.get("llm_model", "gemini-3.8-flash"),
                "llm_api_key": llm_api_key,       # decrypted, in-memory only
            },
            "seen_message_ids": user.get("seen_message_ids", []),
            # Map the gmail_token into the AUTH_ID key so negotiate_creds() finds it
            "gmail-oauth": gmail_token,
        }

    async def list_active_users(self) -> list[str]:
        """Return a list of user_ids that are active and do not need re-auth."""
        if self._db is not None:
            docs = (
                await self._db.collection(FIRESTORE_COLLECTION)
                .where("active", "==", True)
                .where("needs_reauth", "==", False)
                .stream()
            )
            return [doc.id async for doc in docs]
        return [
            uid
            for uid, u in self._local_store.items()
            if u.get("active") and not u.get("needs_reauth")
        ]
