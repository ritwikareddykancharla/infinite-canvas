output "orchestrator_url" {
  description = "Cloud Run orchestration backend URL"
  value       = google_cloud_run_v2_service.orchestrator.uri
}

output "assets_bucket_name" {
  description = "GCS bucket for video assets"
  value       = google_storage_bucket.assets.name
}

output "assets_bucket_url" {
  description = "GCS bucket URL"
  value       = google_storage_bucket.assets.url
}

output "artifact_registry_url" {
  description = "Artifact Registry URL for container images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/infinite-canvas"
}
