# Workload Identity Federation: GitHub Actions presents a short-lived OIDC token,
# GCP exchanges it for a credential that can impersonate ajoa-deployer.
# No long-lived service account keys leave GCP.

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "ajoa-github-pool"
  display_name              = "AJOA GitHub Actions pool"
  description               = "Pool for GitHub OIDC -> deployer SA impersonation."

  depends_on = [google_project_service.enabled]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
    "attribute.repository_ref"   = "assertion.repository + ':' + assertion.ref"
  }

  # Lock the provider to one GitHub org/repo. Without this, *any* GitHub repo
  # could try to mint tokens for our pool. The deployer-SA binding below adds
  # a second wall on top.
  attribute_condition = "assertion.repository == \"${var.github_repo}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Grant the matched principal(s) the ability to impersonate the deployer SA.
# `local.wif_principal` narrows further to a single branch (or "*" for any).
resource "google_service_account_iam_member" "github_can_impersonate_deployer" {
  service_account_id = google_service_account.deployer.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.wif_principal

  depends_on = [google_iam_workload_identity_pool_provider.github]
}
