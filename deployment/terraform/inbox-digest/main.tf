# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# APIs
# ---------------------------------------------------------------------------

locals {
  apis = [
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "cloudscheduler.googleapis.com",
    "firestore.googleapis.com",
    "cloudkms.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudtrace.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.key
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Firestore (Native mode in the project's default database)
# ---------------------------------------------------------------------------

resource "google_firestore_database" "inbox_digest" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Cloud KMS — encrypt user Gmail tokens and LLM API keys
# ---------------------------------------------------------------------------

resource "google_kms_key_ring" "inbox_digest" {
  name       = var.kms_keyring_name
  location   = "global"
  project    = var.project_id
  depends_on = [google_project_service.apis]
}

resource "google_kms_crypto_key" "user_secrets" {
  name            = var.kms_key_name
  key_ring        = google_kms_key_ring.inbox_digest.id
  rotation_period = "7776000s"  # 90 days

  lifecycle {
    prevent_destroy = true
  }
}
