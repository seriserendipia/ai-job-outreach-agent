# Runtime SA — attached to the Cloud Run service. Carries only the IAM needed
# to read its own secrets (granted in secrets.tf). No project-level roles.
resource "google_service_account" "runtime" {
  account_id   = "ajoa-runtime"
  display_name = "AJOA Cloud Run runtime"
  description  = "Identity the Cloud Run service runs as."

  depends_on = [google_project_service.enabled]
}

# Deployer SA — impersonated by GitHub Actions via WIF.
# Holds the roles needed to build/push images and roll out new Cloud Run revisions.
resource "google_service_account" "deployer" {
  account_id   = "ajoa-deployer"
  display_name = "AJOA CI deployer"
  description  = "Impersonated by GitHub Actions via Workload Identity Federation."

  depends_on = [google_project_service.enabled]
}

# Deployer permissions — kept narrow on purpose.
resource "google_project_iam_member" "deployer_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_ar_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

resource "google_project_iam_member" "deployer_cb_editor" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Cloud Build storage (used by `gcloud builds submit`) — needs object admin on
# the auto-created _cloudbuild bucket. roles/storage.admin at project level keeps
# things working with minimal fuss for a portfolio deploy.
resource "google_project_iam_member" "deployer_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Deployer must be able to "actAs" the runtime SA in order to deploy a Cloud
# Run revision that runs as that SA.
resource "google_service_account_iam_member" "deployer_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}
