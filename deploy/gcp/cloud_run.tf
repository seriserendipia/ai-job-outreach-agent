resource "google_cloud_run_v2_service" "backend" {
  name                = var.service_name
  location            = var.region
  deletion_protection = false

  # Public ingress — the only client is a Chrome extension which has no GCP
  # identity. Tighten if a real product fronts it.
  ingress = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.runtime.email

    # min=0 keeps cost at zero when idle. max=2 caps cold-start fan-out for a
    # portfolio demo; bump for real traffic.
    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      resources {
        # 512Mi is plenty for an idle FastAPI; cpu_idle lets the instance fully
        # idle between requests so we don't burn CPU-seconds while parked.
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }

      # Pull secrets in at start as env vars — the app reads them via os.getenv.
      env {
        name = "OPENAI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.openai.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "TAVILY_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.tavily.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        timeout_seconds       = 5
        failure_threshold     = 6
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.enabled,
    google_artifact_registry_repository.backend,
    google_secret_manager_secret_iam_member.runtime_openai_accessor,
    google_secret_manager_secret_iam_member.runtime_tavily_accessor,
    google_secret_manager_secret_version.openai_placeholder,
    google_secret_manager_secret_version.tavily_placeholder,
  ]
}

# Allow unauthenticated HTTPS calls (Chrome extension has no GCP identity).
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  name     = google_cloud_run_v2_service.backend.name
  location = google_cloud_run_v2_service.backend.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
