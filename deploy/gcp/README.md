# `deploy/gcp/` — Terraform + Cloud Build for GCP

Step-by-step deploy from a clean machine. All commands run from this directory
(`deploy/gcp/`) unless noted.

## Prereqs (one-time)

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project ajoa-fwsjvo

# State bucket — bootstrapped out-of-band since Terraform's own state lives in it.
gcloud storage buckets create gs://ajoa-fwsjvo-tfstate \
  --location=us-central1 \
  --uniform-bucket-level-access \
  --public-access-prevention
gcloud storage buckets update gs://ajoa-fwsjvo-tfstate --versioning
```

## First deploy

```bash
cp terraform.tfvars.example terraform.tfvars   # adjust values if needed

terraform init
terraform plan -out=plan.out
terraform apply plan.out
```

The first apply will create the Cloud Run service with a placeholder image
reference (`:latest`). Push a real image and Cloud Run picks it up automatically
because the traffic target is `LATEST`:

```bash
# From repo root:
gcloud builds submit --config=deploy/gcp/cloudbuild.yaml .
```

## Push secret values

```bash
echo -n "$OPENAI_API_KEY" | gcloud secrets versions add OPENAI_API_KEY --data-file=-
echo -n "$TAVILY_API_KEY" | gcloud secrets versions add TAVILY_API_KEY --data-file=-
```

Cloud Run reads `:latest` so the next revision (or a service restart) picks them up.

## Verify

```bash
curl -sf "$(terraform output -raw service_url)/health"
# {"status":"ok"}
```

## CI (GitHub Actions, WIF)

`terraform output workload_identity_provider` and `deployer_service_account`
give you the values to paste into `.github/workflows/deploy.yml` — no JSON key
ever leaves GCP.

## Teardown

```bash
terraform destroy
# Then drop the bootstrap bucket + the whole project:
gcloud storage rm -r gs://ajoa-fwsjvo-tfstate
gcloud projects delete ajoa-fwsjvo
```
