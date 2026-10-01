# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

output "agent_service_url" {
  description = "Internal URL of the ADK agent Cloud Run service."
  value       = google_cloud_run_v2_service.agent.uri
}

output "onboarding_service_url" {
  description = "Public URL of the onboarding web app."
  value       = google_cloud_run_v2_service.onboarding.uri
}

output "pubsub_topic" {
  description = "Pub/Sub topic name for Cloud Scheduler trigger messages."
  value       = google_pubsub_topic.triggers.name
}

output "kms_key_id" {
  description = "KMS crypto key ID for encrypting user secrets."
  value       = google_kms_crypto_key.user_secrets.id
}

output "firestore_database" {
  description = "Firestore database name."
  value       = google_firestore_database.inbox_digest.name
}
