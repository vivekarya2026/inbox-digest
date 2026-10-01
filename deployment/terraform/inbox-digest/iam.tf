# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

# ---------------------------------------------------------------------------
# Service accounts
# ---------------------------------------------------------------------------

# Agent backend service account
resource "google_service_account" "agent_sa" {
  account_id   = "inbox-digest-agent"
  display_name = "Inbox Digest Agent (Cloud Run backend)"
  project      = var.project_id
}

# Onboarding service account
resource "google_service_account" "onboarding_sa" {
  account_id   = "inbox-digest-onboarding"
  display_name = "Inbox Digest Onboarding Web App"
  project      = var.project_id
}

# Pub/Sub invoker (Cloud Scheduler → Pub/Sub → Cloud Run)
resource "google_service_account" "pubsub_invoker" {
  account_id   = "inbox-digest-pubsub-invoker"
  display_name = "Inbox Digest Pub/Sub Cloud Run invoker"
  project      = var.project_id
}

# ---------------------------------------------------------------------------
# Firestore IAM — agent and onboarding can read/write users collection
# ---------------------------------------------------------------------------

resource "google_project_iam_member" "agent_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "onboarding_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.onboarding_sa.email}"
}

# ---------------------------------------------------------------------------
# KMS IAM — agent and onboarding can encrypt/decrypt user secrets
# ---------------------------------------------------------------------------

resource "google_kms_crypto_key_iam_member" "agent_kms" {
  crypto_key_id = google_kms_crypto_key.user_secrets.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_kms_crypto_key_iam_member" "onboarding_kms" {
  crypto_key_id = google_kms_crypto_key.user_secrets.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.onboarding_sa.email}"
}

# ---------------------------------------------------------------------------
# Cloud Trace + Logging
# ---------------------------------------------------------------------------

resource "google_project_iam_member" "agent_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "agent_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# ---------------------------------------------------------------------------
# Pub/Sub invoker → Cloud Run
# ---------------------------------------------------------------------------

resource "google_cloud_run_service_iam_member" "pubsub_invoker" {
  service  = google_cloud_run_v2_service.agent.name
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

# Allow Cloud Scheduler to publish to Pub/Sub on behalf of pubsub_invoker SA
resource "google_project_iam_member" "scheduler_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.pubsub_invoker.email}"
}

# Allow Pub/Sub service agent to use OIDC token for Cloud Run invocation
data "google_project" "project" {}

resource "google_project_iam_member" "pubsub_agent_token" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Onboarding can create Cloud Scheduler jobs
resource "google_project_iam_member" "onboarding_scheduler" {
  project = var.project_id
  role    = "roles/cloudscheduler.admin"
  member  = "serviceAccount:${google_service_account.onboarding_sa.email}"
}
