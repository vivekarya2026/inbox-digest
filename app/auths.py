# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""OAuth 2.0 configuration for Gmail read-only access.

Adapted from core/python/oauth-user-consent-flow/app/auths.py.
Swapped scope from drive.readonly → gmail.readonly.

In local dev (ADK Web UI):
    AUTH_CONFIG is used by the ADK OAuth flow to prompt consent and
    exchange the auth code for tokens.

In the multi-tenant SaaS (Cloud Run + Cloud Scheduler):
    The per-user OAuth token is read from Firestore (encrypted) and
    injected into tool_context.state before the agent run. The
    three-stage negotiate_creds() in tools/gmail.py handles caching
    and refresh automatically.
"""

import os

from fastapi.openapi.models import (
    OAuth2,
    OAuthFlowAuthorizationCode,
    OAuthFlows,
)
from google.adk.auth.auth_credential import (
    AuthCredential,
    AuthCredentialTypes,
    OAuth2Auth,
)
from google.adk.auth.auth_tool import AuthConfig

# --- OAuth 2.0 Endpoints ---
AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# --- Scopes ---
# gmail.readonly: list and read messages; never modify, send, or delete.
SCOPES = {
    "https://www.googleapis.com/auth/gmail.readonly": "Gmail API (read-only)",
}

# --- Token cache key ---
# In the ambient/scheduler path, the per-user token from Firestore is
# injected into tool_context.state under this key before the agent starts.
# In local ADK Web UI dev, negotiate_creds() caches the full credential
# dict here after a successful consent exchange.
TOKEN_CACHE_KEY = os.environ.get("AUTH_ID", "gmail-oauth")

# --- OAuth scheme + credential (used for local ADK Web UI dev only) ---
AUTH_SCHEME = OAuth2(
    flows=OAuthFlows(
        authorizationCode=OAuthFlowAuthorizationCode(
            authorizationUrl=AUTHORIZATION_URL,
            tokenUrl=TOKEN_URL,
            scopes=SCOPES,
        )
    )
)

AUTH_CREDENTIAL = AuthCredential(
    auth_type=AuthCredentialTypes.OAUTH2,
    oauth2=OAuth2Auth(
        client_id=os.environ.get("OAUTH_CLIENT_ID", ""),
        client_secret=os.environ.get("OAUTH_CLIENT_SECRET", ""),
    ),
)

AUTH_CONFIG = AuthConfig(
    auth_scheme=AUTH_SCHEME,
    raw_auth_credential=AUTH_CREDENTIAL,
)
