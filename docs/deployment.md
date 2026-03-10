# Deployment Guide

## Prerequisites

- Python 3.11+
- Node 20+
- Docker + Docker Compose (optional, for full-stack local)
- Google Cloud SDK (`gcloud`) — for GCP deployment
- Terraform ≥ 1.6 — for infrastructure provisioning
- A Gemini API key from [Google AI Studio](https://aistudio.google.com)

---

## Local Development

### Option A: Manual (separate terminals)

**Backend:**
```bash
cd backend
cp .env.example .env
# Edit .env — set GEMINI_API_KEY=your_key
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
# Create .env with:
# REACT_APP_WS_URL=ws://localhost:8000/ws/voice
# REACT_APP_API_URL=http://localhost:8000
npm start
# Opens http://localhost:3000
```

### Option B: Docker Compose (recommended)

```bash
# Copy and configure environment
cp backend/.env.example .env
# Edit .env — set GEMINI_API_KEY

# Build and start both services
docker-compose up --build

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# API docs: http://localhost:8000/docs
```

**Stopping:**
```bash
docker-compose down
```

**Rebuilding after code changes:**
```bash
docker-compose up --build --force-recreate
```

---

## Generate Video Assets (Veo 3.0)

Before deploying, you need the 12 pre-generated video segments in `assets/video/`. Run the generation pipeline:

```bash
# Preview — prints all 12 prompts, no API calls
python scripts/generate_assets.py --dry-run

# Full generation (requires GCP project with Vertex AI + Veo 3.0 enabled)
python scripts/generate_assets.py \
  --project your-gcp-project-id \
  --bucket your-gcs-bucket-name \
  --concurrency 3
```

The script:
1. Generates all 12 scenes via Veo 3.0 on Vertex AI
2. Uploads MP4 files to GCS
3. Writes public CDN URLs back to `assets/metadata/scene_graph.json`

**Generation time:** ~15–30 min at concurrency=3 (Veo 3.0 generation is slow but high quality).

---

## Google Cloud Deployment

### 1. Authenticate

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### 2. Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com
```

### 3. Terraform Apply

```bash
cd infrastructure

# Initialise providers
terraform init

# Preview changes
terraform plan \
  -var="project_id=your-gcp-project-id" \
  -var="gemini_api_key=your-gemini-api-key" \
  -var="region=us-central1"

# Deploy
terraform apply \
  -var="project_id=your-gcp-project-id" \
  -var="gemini_api_key=your-gemini-api-key" \
  -var="region=us-central1"
```

**Resources created:**
- Cloud Run service: `infinite-canvas-backend`
- Cloud Storage bucket: `{project_id}-infinite-canvas-assets`
- Cloud CDN backend bucket
- Artifact Registry repository: `infinite-canvas`
- Secret Manager secret: `gemini-api-key`
- Cloud Monitoring uptime alert

**Outputs:**
```
backend_url  = "https://infinite-canvas-backend-xxxxxxxxxx-uc.a.run.app"
frontend_url = "https://infinite-canvas-frontend-xxxxxxxxxx-uc.a.run.app"
assets_cdn   = "https://storage.googleapis.com/{project_id}-infinite-canvas-assets"
```

### 4. Build and Push Docker Images

```bash
# Backend
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/backend:latest ./backend
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/backend:latest

# Frontend
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/frontend:latest ./frontend
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/frontend:latest
```

Or use Cloud Build:
```bash
gcloud builds submit --config=cloudbuild.yaml .
```

### 5. Deploy to Cloud Run

```bash
# Backend
gcloud run deploy infinite-canvas-backend \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/backend:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest \
  --memory 512Mi \
  --concurrency 80

# Frontend
gcloud run deploy infinite-canvas-frontend \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/frontend:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 256Mi
```

---

## Cloud Run Configuration Details

| Setting | Value | Reason |
|---------|-------|--------|
| Memory | 512Mi (backend) | scipy/numpy audio processing |
| Concurrency | 80 | Each WebSocket = 1 concurrent request; async handles the rest |
| Min instances | 0 | Cost-saving; cold starts are acceptable for this demo |
| Max instances | 10 | Scales for hackathon traffic spikes |
| Timeout | 3600s | Long-lived WebSocket sessions require extended timeout |

**WebSocket note:** Cloud Run supports WebSockets natively on HTTP/2. No special configuration needed.

---

## MCP Server on Cloud Run (optional)

To expose the MCP server for remote ADK agents:

```bash
gcloud run deploy infinite-canvas-mcp \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/backend:latest \
  --command python \
  --args "backend/adk/mcp_server.py" \
  --set-env-vars MCP_TRANSPORT=sse,MCP_PORT=8080 \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080
```

Then connect:
```bash
claude mcp add --transport sse infinite-canvas https://infinite-canvas-mcp-xxxx.run.app/sse
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | yes | — | Google AI / Gemini API key |
| `GCS_BUCKET_NAME` | no | — | GCS bucket for assets (production) |
| `GOOGLE_CLOUD_PROJECT` | no | — | GCP project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | no | — | Path to service account JSON |
| `ALLOWED_ORIGINS` | no | `*` | CORS origins (comma-separated) |
| `GEMINI_MODEL` | no | `gemini-2.0-flash` | ADK agent model |
| `MCP_TRANSPORT` | no | `stdio` | MCP server transport |
| `MCP_PORT` | no | `8001` | MCP SSE port |

---

## Verifying the Deployment

```bash
# Health check
curl https://your-backend.run.app/health
# → {"status": "ok", "service": "infinite-canvas-orchestrator"}

# List scenes
curl https://your-backend.run.app/api/scenes
# → {"scenes": [...], "total": 12}

# Test commentary
curl -X POST https://your-backend.run.app/api/commentary \
  -H "Content-Type: application/json" \
  -d '{"narrative_history": [{"genre": "noir", "beat": "opening"}, {"genre": "horror", "beat": "climax"}]}'
```

---

## Proof of Cloud Deployment (Hackathon Requirement)

The Gemini Live Agent Challenge requires proof of Google Cloud deployment. Use one of:

**Option 1 — Screen recording:**
```bash
# Show Cloud Run service running
gcloud run services describe infinite-canvas-backend --region us-central1

# Show live logs
gcloud run services logs read infinite-canvas-backend --region us-central1 --tail=50
```

**Option 2 — Code evidence:**
- `infrastructure/main.tf` — full Terraform configuration for Cloud Run, GCS, CDN
- `backend/Dockerfile` — container image definition
- `frontend/Dockerfile` — multi-stage production build
- Both services deployed to `us-central1` Cloud Run

The backend uses `google-cloud-storage` and `google-cloud-aiplatform` (Vertex AI / Veo 3.0) — additional evidence of Google Cloud service usage.
