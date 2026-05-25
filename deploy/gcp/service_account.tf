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

# Deployer also needs to actAs *itself* — cloudbuild.yaml sets
# `serviceAccount: ajoa-deployer` so Cloud Build runs builds under this SA.
# A caller can't impersonate any SA (even one it nominally is) without an
# explicit roles/iam.serviceAccountUser binding.
resource "google_service_account_iam_member" "deployer_acts_as_self" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer.email}"
}

# When a build runs as a user-specified SA, that SA needs roles/logging.logWriter
# (cloudbuild.builds.editor doesn't cover it). Without this Cloud Build refuses
# to start the build with "service account requires the role 'roles/logging.logWriter'".
resource "google_project_iam_member" "deployer_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Terraform refresh reads google_project_service resources (it lists enabled
# services on the project). Without this binding the deployer SA hits
# "Permission denied to list services" the moment GHA runs `terraform apply`.
resource "google_project_iam_member" "deployer_serviceusage_admin" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageAdmin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Terraform reads Secret Manager resources during refresh as well (versions,
# IAM, etc.). secretmanager.admin is the catch-all that covers list + read.
# (Runtime SA only gets per-secret accessor; deployer gets project-wide admin
# because Terraform iterates over all secrets it manages.)
resource "google_project_iam_member" "deployer_secret_admin" {
  project = var.project_id
  role    = "roles/secretmanager.admin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Terraform refresh reads SAs and their IAM policies (e.g. runtime SA, WIF
# bindings). roles/iam.securityAdmin covers reading + writing SA IAM policies.
resource "google_project_iam_member" "deployer_iam_security_admin" {
  project = var.project_id
  role    = "roles/iam.securityAdmin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}

# Terraform refresh reads Workload Identity Pools / providers it manages. The
# iam.workloadIdentityPoolAdmin role covers list + read + write on those.
resource "google_project_iam_member" "deployer_wif_admin" {
  project = var.project_id
  role    = "roles/iam.workloadIdentityPoolAdmin"
  member  = "serviceAccount:${google_service_account.deployer.email}"
}
