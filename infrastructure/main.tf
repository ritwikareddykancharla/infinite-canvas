terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
  backend "gcs" {
    bucket = "infinite-canvas-tfstate"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Cloud Storage: Video Assets ──────────────────────────────────────────────
resource "google_storage_bucket" "assets" {
  name                        = "${var.project_id}-infinite-canvas-assets"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "OPTIONS"]
    response_header = ["Content-Type", "Accept-Ranges", "Content-Range"]
    max_age_seconds = 3600
  }

  lifecycle_rule {
    condition { age = 365 }
    action { type = "SetStorageClass"; storage_class = "NEARLINE" }
  }
}

resource "google_storage_bucket_iam_member" "assets_public_read" {
  bucket = google_storage_bucket.assets.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# ── Cloud CDN + Load Balancer for Assets ─────────────────────────────────────
resource "google_compute_backend_bucket" "assets_cdn" {
  name        = "infinite-canvas-assets-cdn"
  bucket_name = google_storage_bucket.assets.name
  enable_cdn  = true

  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    client_ttl        = 3600
    default_ttl       = 3600
    max_ttl           = 86400
    serve_while_stale = 86400
  }
}

# ── Artifact Registry for Container Images ───────────────────────────────────
resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = "infinite-canvas"
  format        = "DOCKER"
  description   = "InfiniteCanvas application containers"
}

# ── Cloud Run: Orchestration Backend ─────────────────────────────────────────
resource "google_cloud_run_v2_service" "orchestrator" {
  name     = "infinite-canvas-orchestrator"
  location = var.region

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/infinite-canvas/backend:latest"

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
        cpu_idle = true
      }

      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.assets.name
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
    }

    service_account = google_service_account.orchestrator.email
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [google_secret_manager_secret_version.gemini_api_key]
}

resource "google_cloud_run_v2_service_iam_member" "orchestrator_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.orchestrator.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ── Service Account for Cloud Run ────────────────────────────────────────────
resource "google_service_account" "orchestrator" {
  account_id   = "infinite-canvas-run"
  display_name = "InfiniteCanvas Cloud Run Service Account"
}

resource "google_project_iam_member" "orchestrator_gcs" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_project_iam_member" "orchestrator_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

resource "google_project_iam_member" "orchestrator_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.orchestrator.email}"
}

# ── Secret Manager: Gemini API Key ───────────────────────────────────────────
resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "gemini-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "gemini_api_key" {
  secret      = google_secret_manager_secret.gemini_api_key.id
  secret_data = var.gemini_api_key
}

# ── Cloud Monitoring: Latency Alerts ─────────────────────────────────────────
resource "google_monitoring_alert_policy" "high_latency" {
  display_name = "InfiniteCanvas High Latency Alert"
  combiner     = "OR"

  conditions {
    display_name = "Cloud Run Request Latency > 1s"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_latencies\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 1000
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }

  notification_channels = []
  alert_strategy {
    auto_close = "604800s"
  }
}
