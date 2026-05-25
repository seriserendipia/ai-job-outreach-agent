# Secret *containers*. Their values are written out-of-band (gcloud secrets
# versions add) — Terraform never holds plaintext credentials in state.

resource "google_secret_manager_secret" "openai" {
  secret_id = "OPENAI_API_KEY"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret" "tavily" {
  secret_id = "TAVILY_API_KEY"

  replication {
    auto {}
  }

  depends_on = [google_project_service.enabled]
}

# Placeholder versions — Cloud Run refuses to start if the referenced
# `:latest` version doesn't exist. The real value is pushed out-of-band via
# `gcloud secrets versions add`. `ignore_changes = [secret_data]` keeps
# Terraform from clobbering whatever the operator pushed in.
resource "google_secret_manager_secret_version" "openai_placeholder" {
  secret      = google_secret_manager_secret.openai.id
  secret_data = "PLACEHOLDER_REPLACE_VIA_GCLOUD_SECRETS_VERSIONS_ADD"

  lifecycle {
    ignore_changes = [secret_data, enabled]
  }
}

resource "google_secret_manager_secret_version" "tavily_placeholder" {
  secret      = google_secret_manager_secret.tavily.id
  secret_data = "PLACEHOLDER_REPLACE_VIA_GCLOUD_SECRETS_VERSIONS_ADD"

  lifecycle {
    ignore_changes = [secret_data, enabled]
  }
}

# Runtime SA reads each secret. Scoped per-secret instead of at project level.
resource "google_secret_manager_secret_iam_member" "runtime_openai_accessor" {
  secret_id = google_secret_manager_secret.openai.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "runtime_tavily_accessor" {
  secret_id = google_secret_manager_secret.tavily.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}
