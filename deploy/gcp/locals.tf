data "google_project" "current" {
  project_id = var.project_id
}

locals {
  project_number = data.google_project.current.number

  ar_repo_url = "${var.region}-docker.pkg.dev/${var.project_id}/${var.service_name}"

  # Secret Manager secret ids the runtime SA must be able to access.
  runtime_secret_ids = [
    google_secret_manager_secret.openai.secret_id,
    google_secret_manager_secret.tavily.secret_id,
  ]

  # WIF principal — the OIDC subject claim shape GitHub Actions presents.
  # ref is locked to a single branch unless var.github_branch == "*".
  wif_principal = (
    var.github_branch == "*"
    ? "principalSet://iam.googleapis.com/projects/${local.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/attribute.repository/${var.github_repo}"
    : "principalSet://iam.googleapis.com/projects/${local.project_number}/locations/global/workloadIdentityPools/${google_iam_workload_identity_pool.github.workload_identity_pool_id}/attribute.repository_ref/${var.github_repo}:refs/heads/${var.github_branch}"
  )
}
