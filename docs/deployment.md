# Deploying & Testing InfiniteCanvas on GCP

## API Key: Vertex AI vs AI Studio

The backend uses `google-genai` SDK for Gemini Live. It supports two auth modes:

| Mode | When to use | What you need |
|------|-------------|---------------|
| **Vertex AI** (recommended for GCP) | You have a GCP project with Vertex AI enabled | `gcloud auth`, project ID |
| **AI Studio API key** | You have a key from aistudio.google.com | The API key string |

**If you have a Vertex AI API key from Google Cloud Console** — that key goes in `GEMINI_API_KEY` in your `.env` and the code works as-is.

**If you want to use ADC (service account / `gcloud auth`)** — see [Using Vertex AI with ADC](#using-vertex-ai-with-adc) below.

---

## 1. Run Locally First

This is the fastest way to verify everything works before touching GCP.

### Clone & configure

```bash
cd backend
cp .env.example .env
```

Edit `.env`:
```
GEMINI_API_KEY=<your key here>
GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
GCS_BUCKET_NAME=<your-bucket-name>   # can be anything for local testing
ALLOWED_ORIGINS=http://localhost:3000
```

### Start the backend

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Check it's alive:
```bash
curl http://localhost:8000/health
# → {"status": "ok", "service": "infinite-canvas-orchestrator"}

curl http://localhost:8000/api/scenes
# → {"scenes": [...], "total": 12}
```

### Start the frontend

```bash
cd frontend
npm install
npm start
# Opens http://localhost:3000
```

Open the browser, allow microphone when prompted. The voice pipeline will be active. Try clicking the genre buttons first (they call `POST /api/intent` directly, no voice needed) to confirm the scene switching works.

### Test the voice pipeline without a microphone

```bash
# Manually inject an intent — simulates what Gemini Live would produce
curl -X POST http://localhost:8000/api/intent \
  -H "Content-Type: application/json" \
  -d '{"genre": "horror", "action": "change_genre", "confidence": 0.9, "emotional_intensity": 0.8}'
```

The frontend should switch to horror visuals and audio.

```bash
# Advance to next beat
curl -X POST http://localhost:8000/api/intent \
  -H "Content-Type: application/json" \
  -d '{"action": "next_beat", "confidence": 1.0}'

# Reset
curl -X POST http://localhost:8000/api/intent \
  -H "Content-Type: application/json" \
  -d '{"action": "reset", "confidence": 1.0}'
```

### Test commentary endpoint

```bash
curl -X POST http://localhost:8000/api/commentary \
  -H "Content-Type: application/json" \
  -d '{
    "narrative_history": [
      {"genre": "noir", "beat": "opening"},
      {"genre": "horror", "beat": "confrontation"},
      {"genre": "horror", "beat": "climax"}
    ]
  }'
```

---

## 2. Using Vertex AI with ADC

If you want to use Application Default Credentials instead of an API key, update `backend/gemini/live_client.py` where the client is initialised:

```python
# Current (API key):
self._client = genai.Client(api_key=self.api_key)

# Change to (Vertex AI + ADC):
self._client = genai.Client(
    vertexai=True,
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location="us-central1",
)
```

Then authenticate locally:
```bash
gcloud auth application-default login
```

And in `.env`, leave `GEMINI_API_KEY` blank — the code will fall through to ADC. The `GeminiLiveClient` skips the API key check if you change the client init as above.

On Cloud Run, ADC is automatic — the service account attached to the Cloud Run service handles authentication. No key management needed.

---

## 3. Enable Required GCP APIs

```bash
gcloud config set project YOUR_PROJECT_ID

gcloud services enable \
  run.googleapis.com \
  storage.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com
```

---

## 4. Build & Push the Docker Image

```bash
# Configure Docker to use gcloud credentials
gcloud auth configure-docker us-central1-docker.pkg.dev

# Create the Artifact Registry repo (one-time)
gcloud artifacts repositories create infinite-canvas \
  --repository-format=docker \
  --location=us-central1

# Build and push
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/backend:latest ./backend
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/backend:latest

docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/frontend:latest ./frontend
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/infinite-canvas/frontend:latest
```

---

## 5. Deploy with Terraform

The Terraform config in `infrastructure/` creates everything: Cloud Run, GCS bucket, CDN, service account, Secret Manager entry, and a latency alert.

```bash
cd infrastructure

# One-time: create the state bucket
gsutil mb -l us-central1 gs://YOUR_PROJECT-tfstate

terraform init

terraform apply \
  -var="project_id=YOUR_PROJECT_ID" \
  -var="gemini_api_key=YOUR_KEY" \
  -var="region=us-central1"
```

Terraform outputs the backend and CDN URLs when done.

### What Terraform creates

| Resource | Name |
|----------|------|
| Cloud Run | `infinite-canvas-orchestrator` |
| GCS bucket | `{project_id}-infinite-canvas-assets` |
| Cloud CDN | attached to the GCS bucket |
| Artifact Registry | `infinite-canvas` |
| Service Account | `infinite-canvas-run@...` |
| Secret | `gemini-api-key` in Secret Manager |
| Alert | Cloud Run latency > 1s |

The Cloud Run service account gets `roles/storage.objectAdmin` (to serve assets), `roles/aiplatform.user` (for Vertex AI), and `roles/secretmanager.secretAccessor` (for the API key).

---

## 6. Deploy to Cloud Run (without Terraform)

If you want to skip Terraform and deploy manually:

```bash
# Store the API key in Secret Manager
echo -n "YOUR_GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
  --data-file=-

# Create a service account
gcloud iam service-accounts create infinite-canvas-run \
  --display-name="InfiniteCanvas Cloud Run SA"

# Grant it the roles it needs
PROJECT=$(gcloud config get-value project)
SA="infinite-canvas-run@${PROJECT}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" --role="roles/storage.objectAdmin"
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"

# Deploy the backend
gcloud run deploy infinite-canvas-orchestrator \
  --image us-central1-docker.pkg.dev/${PROJECT}/infinite-canvas/backend:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account $SA \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest \
  --set-env-vars GOOGLE_CLOUD_PROJECT=${PROJECT} \
  --memory 1Gi \
  --cpu 2 \
  --timeout 3600 \
  --port 8000

# Deploy the frontend
gcloud run deploy infinite-canvas-frontend \
  --image us-central1-docker.pkg.dev/${PROJECT}/infinite-canvas/frontend:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 256Mi \
  --port 80
```

Note `--timeout 3600` on the backend — required for long-lived WebSocket sessions.

---

## 7. Verify the Deployment

```bash
BACKEND=$(gcloud run services describe infinite-canvas-orchestrator \
  --region us-central1 --format='value(status.url)')

# Health check
curl $BACKEND/health
# → {"status": "ok", "service": "infinite-canvas-orchestrator"}

# Scene list
curl $BACKEND/api/scenes

# Inject a test intent
curl -X POST $BACKEND/api/intent \
  -H "Content-Type: application/json" \
  -d '{"genre": "scifi", "action": "change_genre", "confidence": 0.95}'

# Check logs
gcloud run services logs read infinite-canvas-orchestrator \
  --region us-central1 --tail 50
```

---

## 8. Upload Video Assets to GCS

After creating the GCS bucket (Terraform does this), upload your pre-generated video segments:

```bash
BUCKET="${PROJECT}-infinite-canvas-assets"

# Upload all segments
gsutil -m cp assets/video/*.mp4 gs://$BUCKET/video/
gsutil -m cp assets/audio/*.wav gs://$BUCKET/audio/
gsutil -m cp assets/metadata/*.json gs://$BUCKET/metadata/

# Make them publicly readable
gsutil iam ch allUsers:objectViewer gs://$BUCKET
```

Or run the Veo 3.0 generation pipeline to generate them from scratch:

```bash
python scripts/generate_assets.py \
  --project $PROJECT \
  --bucket $BUCKET \
  --concurrency 3
```

---

## 9. Set the Frontend Backend URL

The frontend needs to know where the backend is. Set `REACT_APP_WS_URL` and `REACT_APP_API_URL` at build time:

```bash
BACKEND_URL=$(gcloud run services describe infinite-canvas-orchestrator \
  --region us-central1 --format='value(status.url)')

docker build \
  --build-arg REACT_APP_WS_URL="wss://${BACKEND_URL#https://}/ws/voice" \
  --build-arg REACT_APP_API_URL="$BACKEND_URL" \
  -t us-central1-docker.pkg.dev/${PROJECT}/infinite-canvas/frontend:latest \
  ./frontend

docker push us-central1-docker.pkg.dev/${PROJECT}/infinite-canvas/frontend:latest

gcloud run deploy infinite-canvas-frontend \
  --image us-central1-docker.pkg.dev/${PROJECT}/infinite-canvas/frontend:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 256Mi
```

---

## Common Issues

**WebSocket disconnects immediately on Cloud Run**
Add `--timeout 3600` to the Cloud Run deploy command. The default 300s timeout kills long-lived WebSocket connections.

**`GEMINI_API_KEY not set — using mock intent generator` in logs**
The secret is not being injected. Check the service account has `roles/secretmanager.secretAccessor` and the secret name matches exactly.

**CORS errors in browser**
Set `ALLOWED_ORIGINS` to your frontend Cloud Run URL:
```bash
gcloud run services update infinite-canvas-orchestrator \
  --region us-central1 \
  --set-env-vars ALLOWED_ORIGINS=https://your-frontend-url.run.app
```

**Assets 404**
Videos aren't in GCS yet. Either upload them manually or run `generate_assets.py`. Local fallback: place MP4 files in `backend/assets/video/` and they'll be served from the static mount.
