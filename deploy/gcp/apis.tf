# Idempotent enablement — bootstrap already turned these on via gcloud, but
# Terraform takes ownership so `apply` from a clean project also works.
# disable_on_destroy = false so `terraform destroy` doesn't break sibling work.
locals {
  required_apis = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "storage.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
  ])
}

resource "google_project_service" "enabled" {
  for_each           = local.required_apis
  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}
