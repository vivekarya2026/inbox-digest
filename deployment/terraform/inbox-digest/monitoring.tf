# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

# ---------------------------------------------------------------------------
# Cloud Monitoring — alert on digest failures and dead-letter messages
# ---------------------------------------------------------------------------

# Alert when messages land in the dead-letter topic (delivery failures)
resource "google_logging_metric" "dead_letter_messages" {
  name    = "inbox_digest/dead_letter_messages"
  project = var.project_id

  filter = <<-EOT
    resource.type="pubsub_subscription"
    resource.labels.subscription_id="${google_pubsub_subscription.trigger_push.name}-dead-letter"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# Alert when the agent logs a digest send failure
resource "google_logging_metric" "digest_send_failed" {
  name    = "inbox_digest/send_failed"
  project = var.project_id

  filter = <<-EOT
    resource.type="cloud_run_revision"
    resource.labels.service_name="${var.agent_service_name}"
    jsonPayload.event="digest_send_failed"
  EOT

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }
}

# Notification channel
resource "google_monitoring_notification_channel" "ops_email" {
  display_name = "Inbox Digest Ops Email"
  type         = "email"
  project      = var.project_id

  labels = {
    email_address = var.notification_email
  }
}

# Alert policy: fire if any dead-letter messages appear
resource "google_monitoring_alert_policy" "dead_letter_alert" {
  display_name = "Inbox Digest: Dead-letter messages"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "Dead-letter subscription has messages"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.dead_letter_messages.name}\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.ops_email.id]
  severity              = "WARNING"
}

# Alert policy: fire if any send failures appear
resource "google_monitoring_alert_policy" "send_failed_alert" {
  display_name = "Inbox Digest: WhatsApp send failures"
  project      = var.project_id
  combiner     = "OR"

  conditions {
    display_name = "WhatsApp send failures > 0"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.digest_send_failed.name}\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_COUNT"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.ops_email.id]
  severity              = "WARNING"
}
