# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run, Firestore, and Pub/Sub."
  type        = string
  default     = "us-central1"
}

variable "agent_service_name" {
  description = "Cloud Run service name for the ADK agent backend."
  type        = string
  default     = "inbox-digest-agent"
}

variable "onboarding_service_name" {
  description = "Cloud Run service name for the onboarding web app."
  type        = string
  default     = "inbox-digest-onboarding"
}

variable "agent_name" {
  description = "ADK agent name (must match the agents_dir subdirectory name)."
  type        = string
  default     = "app"
}

variable "agent_image" {
  description = "Container image URI for the ADK agent Cloud Run service."
  type        = string
}

variable "onboarding_image" {
  description = "Container image URI for the onboarding Cloud Run service."
  type        = string
}

variable "pubsub_topic_name" {
  description = "Pub/Sub topic name for hourly trigger messages."
  type        = string
  default     = "inbox-digest-triggers"
}

variable "notification_email" {
  description = "Email for ops alerts (digest failures, quota errors, etc.)."
  type        = string

  validation {
    condition     = can(regex("^[^@]+@[^@]+$", var.notification_email))
    error_message = "A valid email address is required for notification_email."
  }
}

variable "kms_keyring_name" {
  description = "Cloud KMS keyring name for encrypting user secrets."
  type        = string
  default     = "inbox-digest-keyring"
}

variable "kms_key_name" {
  description = "Cloud KMS crypto key name for encrypting user secrets."
  type        = string
  default     = "user-secrets"
}
