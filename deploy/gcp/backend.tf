# Remote state on GCS. The bucket is bootstrapped out-of-band (gcloud storage
# buckets create) before `terraform init`, since the state itself can't live in
# a bucket that doesn't exist yet.
terraform {
  backend "gcs" {
    bucket = "ajoa-fwsjvo-tfstate"
    prefix = "ajoa-backend"
  }
}
