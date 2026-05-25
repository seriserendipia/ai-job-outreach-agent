resource "google_artifact_registry_repository" "backend" {
  location      = var.region
  repository_id = var.service_name
  description   = "Container images for the AJOA backend."
  format        = "DOCKER"

  depends_on = [google_project_service.enabled]
}
