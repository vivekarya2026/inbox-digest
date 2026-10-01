# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

# ---------------------------------------------------------------------------
# Secret Manager — WhatsApp API credentials (operator-level)
# These are separate from per-user secrets (which use KMS + Firestore)
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "whatsapp_api_token" {
  secret_id = "whatsapp-api-token"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret" "whatsapp_phone_number_id" {
  secret_id = "whatsapp-phone-number-id"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "session_secret" {
  secret_id = "onboarding-session-secret"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "google_client_secret" {
  secret_id = "google-oauth-client-secret"
  project   = var.project_id

  replication {
    auto {}
  }
}

# Grant agent read access to WhatsApp secrets
resource "google_secret_manager_secret_iam_member" "agent_whatsapp_token" {
  secret_id = google_secret_manager_secret.whatsapp_api_token.secret_id
  project   = var.project_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "agent_phone_number_id" {
  secret_id = google_secret_manager_secret.whatsapp_phone_number_id.secret_id
  project   = var.project_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.agent_sa.email}"
}

# Grant onboarding access to OAuth client secret and session secret
resource "google_secret_manager_secret_iam_member" "onboarding_session" {
  secret_id = google_secret_manager_secret.session_secret.secret_id
  project   = var.project_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.onboarding_sa.email}"
}

resource "google_secret_manager_secret_iam_member" "onboarding_google_secret" {
  secret_id = google_secret_manager_secret.google_client_secret.secret_id
  project   = var.project_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.onboarding_sa.email}"
}

# ---------------------------------------------------------------------------
# Cloud Run — Agent backend
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "agent" {
  name     = var.agent_service_name
  location = var.region
  project  = var.project_id

  # No public ingress — only Pub/Sub push (authenticated OIDC)
  ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.agent_sa.email

    scaling {
      min_instance_count = 1   # keep warm to avoid cold-start timeouts
      max_instance_count = 10
    }

    containers {
      image = var.agent_image

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "FIRESTORE_COLLECTION"
        value = "users"
      }
      env {
        name  = "GOOGLE_KMS_KEY_NAME"
        value = "${google_kms_crypto_key.user_secrets.id}"
      }
      env {
        name  = "PUBSUB_TOPIC_NAME"
        value = var.pubsub_topic_name
      }
      # WhatsApp credentials from Secret Manager
      env {
        name = "WHATSAPP_API_TOKEN"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.whatsapp_api_token.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "WHATSAPP_PHONE_NUMBER_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.whatsapp_phone_number_id.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 10
        period_seconds        = 5
        failure_threshold     = 5
      }
    }
  }

  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Cloud Run — Onboarding web app (public ingress)
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "onboarding" {
  name     = var.onboarding_service_name
  location = var.region
  project  = var.project_id

  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.onboarding_sa.email

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = var.onboarding_image

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "FIRESTORE_COLLECTION"
        value = "users"
      }
      env {
        name  = "GOOGLE_KMS_KEY_NAME"
        value = "${google_kms_crypto_key.user_secrets.id}"
      }
      env {
        name  = "PUBSUB_TOPIC_NAME"
        value = var.pubsub_topic_name
      }
      env {
        name  = "AGENT_TRIGGER_URL"
        value = google_cloud_run_v2_service.agent.uri
      }
      env {
        name  = "OIDC_SERVICE_ACCOUNT"
        value = google_service_account.pubsub_invoker.email
      }
      env {
        name = "SESSION_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.session_secret.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "GOOGLE_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.google_client_secret.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  depends_on = [google_project_service.apis]
}

# Allow unauthenticated access to the onboarding web app
resource "google_cloud_run_service_iam_member" "onboarding_public" {
  service  = google_cloud_run_v2_service.onboarding.name
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "allUsers"
}
