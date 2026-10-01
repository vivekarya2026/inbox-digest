# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

# ---------------------------------------------------------------------------
# Pub/Sub topic + push subscription → ADK ambient trigger endpoint
# ---------------------------------------------------------------------------

resource "google_pubsub_topic" "triggers" {
  name    = var.pubsub_topic_name
  project = var.project_id

  depends_on = [google_project_service.apis]
}

# Dead-letter topic for failed deliveries
resource "google_pubsub_topic" "dead_letter" {
  name    = "${var.pubsub_topic_name}-dead-letter"
  project = var.project_id

  depends_on = [google_project_service.apis]
}

# Push subscription — each message pushed to /trigger/pubsub on the agent service.
# Cloud Scheduler publishes per-user messages; subscription path = user_id.
resource "google_pubsub_subscription" "trigger_push" {
  name    = "${var.pubsub_topic_name}-push"
  project = var.project_id
  topic   = google_pubsub_topic.triggers.id

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.agent.uri}/apps/${var.agent_name}/trigger/pubsub"

    oidc_token {
      service_account_email = google_service_account.pubsub_invoker.email
      audience              = google_cloud_run_v2_service.agent.uri
    }
  }

  # 60-second ack deadline — each user's hourly run must finish within 60s
  ack_deadline_seconds = 60

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "300s"
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 3
  }

  expiration_policy {
    ttl = ""
  }

  depends_on = [google_cloud_run_v2_service.agent]
}
