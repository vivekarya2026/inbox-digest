# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

"""Structured logging + Cloud Trace helpers for Inbox Digest.

All agent runs emit JSON-structured logs captured by Cloud Run →
Cloud Logging. A log-based metric fires an alert via Cloud Monitoring
when digest_send_failed events appear.

Usage:
  from app.observability import log_run_start, log_run_complete, log_error

These are thin wrappers that emit structured JSON to stdout (the Cloud Run
log capture path). They also emit OpenTelemetry spans when the ADK
otel_to_cloud integration is active.
"""

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

_SERVICE_NAME = "inbox-digest-agent"
_VERSION = os.environ.get("K_REVISION", "local")


def _emit(severity: str, event: str, user_id: str, **fields: Any) -> None:
    """Emit a structured JSON log entry to stdout (Cloud Run → Cloud Logging)."""
    entry = {
        "severity": severity,
        "service": _SERVICE_NAME,
        "version": _VERSION,
        "event": event,
        "user_id": user_id,
        "timestamp": datetime.now(tz=UTC).isoformat(),
        **{k: v for k, v in fields.items() if v is not None},
    }
    print(json.dumps(entry), flush=True)


# ---------------------------------------------------------------------------
# Per-run lifecycle events
# ---------------------------------------------------------------------------


def log_run_start(user_id: str, *, trigger: str = "scheduler") -> None:
    """Log the start of a digest run."""
    _emit("INFO", "digest_run_start", user_id, trigger=trigger)


def log_run_complete(
    user_id: str,
    *,
    sent: bool,
    p1_count: int = 0,
    p2_count: int = 0,
    total_fetched: int = 0,
    total_filtered: int = 0,
    duration_ms: float | None = None,
    skip_reason: str | None = None,
) -> None:
    """Log the outcome of a completed digest run."""
    _emit(
        "INFO",
        "digest_run_complete",
        user_id,
        sent=sent,
        p1_count=p1_count,
        p2_count=p2_count,
        total_fetched=total_fetched,
        total_filtered=total_filtered,
        duration_ms=duration_ms,
        skip_reason=skip_reason,
    )


def log_digest_sent(
    user_id: str,
    *,
    p1_count: int,
    p2_count: int,
    provider: str,
    message_id: str | None = None,
) -> None:
    """Log a successful WhatsApp digest delivery."""
    _emit(
        "INFO",
        "digest_sent",
        user_id,
        p1_count=p1_count,
        p2_count=p2_count,
        provider=provider,
        message_id=message_id,
    )


def log_digest_skipped(user_id: str, *, reason: str) -> None:
    """Log a run that produced no digest (expected — no P1/P2)."""
    _emit("INFO", "digest_skipped", user_id, reason=reason)


def log_send_failed(user_id: str, *, provider: str, error: str) -> None:
    """Log a failed WhatsApp delivery — triggers Cloud Monitoring alert.

    The alert_type field is matched by the log-based metric in monitoring.tf.
    """
    _emit(
        "WARNING",
        "digest_send_failed",
        user_id,
        alert_type="digest_send_failed",
        provider=provider,
        error=error[:500],
    )


def log_needs_reauth(user_id: str, *, reason: str) -> None:
    """Log that a user's Gmail OAuth token needs renewal."""
    _emit("WARNING", "needs_reauth", user_id, reason=reason)


def log_error(user_id: str, *, error: str, context: str = "") -> None:
    """Log an unexpected error in a digest run."""
    _emit("ERROR", "digest_error", user_id, error=error[:1000], context=context)
