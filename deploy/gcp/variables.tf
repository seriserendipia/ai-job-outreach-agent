variable "project_id" {
  description = "GCP project id (must already exist with billing enabled)."
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Run and Artifact Registry."
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service name and Artifact Registry repo name."
  type        = string
  default     = "ajoa-backend"
}

variable "image" {
  description = <<EOT
Full container image reference Cloud Run should serve.

Defaults to a public Google "hello" placeholder so the first `terraform apply`
succeeds before any image has been pushed to Artifact Registry. After the first
image is pushed, override this (via -var or tfvars) to the AR path, e.g.:

  us-central1-docker.pkg.dev/ajoa-fwsjvo/ajoa-backend/ajoa-backend:latest

Changing this triggers a new Cloud Run revision.
EOT
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "github_repo" {
  description = "GitHub repo allowed to assume the deployer SA via WIF, in 'owner/repo' form."
  type        = string
  default     = "seriserendipia/ai-job-outreach-agent"
}

variable "github_branch" {
  description = "GitHub branch ref allowed by WIF. Set to '*' to allow any branch."
  type        = string
  default     = "master"
}
