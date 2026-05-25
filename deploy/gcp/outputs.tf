output "service_url" {
  description = "Public HTTPS URL of the Cloud Run service."
  value       = google_cloud_run_v2_service.backend.uri
}

output "artifact_registry_repo" {
  description = "Artifact Registry repo path (push image with: docker push <this>/<name>:<tag>)."
  value       = local.ar_repo_url
}

output "runtime_service_account" {
  description = "Email of the runtime SA the Cloud Run service runs as."
  value       = google_service_account.runtime.email
}

output "deployer_service_account" {
  description = "Email of the deployer SA impersonated by GitHub Actions."
  value       = google_service_account.deployer.email
}

output "workload_identity_provider" {
  description = "Full resource name of the WIF provider — paste into GHA google-github-actions/auth."
  value       = "projects/${local.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/providers/${google_iam_workload_identity_pool_provider.github.workload_identity_pool_provider_id}"
}

output "project_id" {
  description = "GCP project id (echoed for convenience in GHA outputs)."
  value       = var.project_id
}

output "region" {
  value = var.region
}
