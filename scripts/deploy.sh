#!/bin/bash
# scripts/deploy.sh
# ══════════════════════════════════════════════════════════════════
# One-shot deploy script for Cloud Run.
# Run this once — after that use cloudbuild.yaml for CI/CD.
#
# Usage:
#   chmod +x scripts/deploy.sh
#   ./scripts/deploy.sh
# ══════════════════════════════════════════════════════════════════

set -e  # exit on any error

PROJECT_ID="project-agent-491814"
REGION="us-central1"
SERVICE="hr-gateway"
IMAGE="gcr.io/$PROJECT_ID/$SERVICE"

echo "🚀 Deploying HR Gateway to Cloud Run..."
echo "   Project : $PROJECT_ID"
echo "   Region  : $REGION"
echo "   Service : $SERVICE"
echo ""

# ── Step 1: Enable required APIs ──────────────────────────────────────────────
echo "📦 Step 1: Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  containerregistry.googleapis.com \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  --project=$PROJECT_ID

echo "✅ APIs enabled"

# ── Step 2: Create service account ────────────────────────────────────────────
echo ""
echo "🔐 Step 2: Creating service account..."
gcloud iam service-accounts create hr-gateway-sa \
  --display-name="HR Gateway Service Account" \
  --project=$PROJECT_ID 2>/dev/null || echo "   Service account already exists"

SA="hr-gateway-sa@$PROJECT_ID.iam.gserviceaccount.com"

# Grant required roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" \
  --role="roles/aiplatform.user" --quiet

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" \
  --role="roles/cloudsql.client" --quiet

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA" \
  --role="roles/secretmanager.secretAccessor" --quiet

echo "✅ Service account configured"

# ── Step 3: Create secrets in Secret Manager ──────────────────────────────────
echo ""
echo "🔑 Step 3: Setting up secrets..."

create_secret() {
  local name=$1
  local value=$2
  if gcloud secrets describe $name --project=$PROJECT_ID &>/dev/null; then
    echo "   $name already exists — updating..."
    echo -n "$value" | gcloud secrets versions add $name --data-file=- --project=$PROJECT_ID
  else
    echo -n "$value" | gcloud secrets create $name --data-file=- --project=$PROJECT_ID
    echo "   $name created"
  fi
}

# Prompt for secret values
read -p "Enter JWT_SECRET_KEY (min 32 chars): " JWT_SECRET
read -p "Enter LANGSMITH_API_KEY (or press Enter to skip): " LANGSMITH_KEY
read -p "Enter ALLOYDB_DB_PASS: " ALLOYDB_PASS

create_secret "jwt-secret" "$JWT_SECRET"
[ -n "$LANGSMITH_KEY" ] && create_secret "langsmith-api-key" "$LANGSMITH_KEY"
create_secret "alloydb-password" "$ALLOYDB_PASS"

echo "✅ Secrets stored"

# ── Step 4: Build and push Docker image ───────────────────────────────────────
echo ""
echo "🐳 Step 4: Building Docker image..."
gcloud builds submit \
  --tag $IMAGE:latest \
  --project=$PROJECT_ID \
  .

echo "✅ Image built and pushed"

# ── Step 5: Deploy to Cloud Run ───────────────────────────────────────────────
echo ""
echo "☁️  Step 5: Deploying to Cloud Run..."
gcloud run deploy $SERVICE \
  --image=$IMAGE:latest \
  --region=$REGION \
  --platform=managed \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=10 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --concurrency=10 \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION,ALLOYDB_USE_CONNECTOR=true,LANGSMITH_TRACING=true" \
  --set-secrets="JWT_SECRET_KEY=jwt-secret:latest,LANGSMITH_API_KEY=langsmith-api-key:latest,ALLOYDB_DB_PASS=alloydb-password:latest" \
  --service-account=$SA \
  --project=$PROJECT_ID

# ── Step 6: Get the live URL ──────────────────────────────────────────────────
echo ""
SERVICE_URL=$(gcloud run services describe $SERVICE \
  --region=$REGION \
  --project=$PROJECT_ID \
  --format="value(status.url)")

echo "════════════════════════════════════════════════════"
echo "✅ DEPLOYMENT COMPLETE"
echo "════════════════════════════════════════════════════"
echo "🌐 Live URL : $SERVICE_URL"
echo "📖 Docs     : $SERVICE_URL/docs"
echo "❤️  Health   : $SERVICE_URL/api/v1/health"
echo ""
echo "Test it:"
echo "  curl $SERVICE_URL/api/v1/health"