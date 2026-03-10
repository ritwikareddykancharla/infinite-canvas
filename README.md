# InfiniteCanvas: The Liquid Movie

> The first film that rewrites itself while you watch. Speak, and reality reshapes.

**Gemini Live Agent Challenge** — Built for the hackathon.

---

## What It Does

InfiniteCanvas is a voice-controlled cinematic experience where viewers become directors of a live-changing reality.

- **Watch** — A 90-second cinematic scene (two people, one secret, infinite possibilities)
- **Speak** — Say "make it noir," "she's the villain," "cyberpunk now"
- **Witness** — The film instantly transforms — same moment, entirely new reality

### Genres
| Genre | Vibe | Transition |
|-------|------|------------|
| Noir | Shadows, moral ambiguity, jazz | Glitch dissolve |
| Rom-Com | Golden light, warmth, piano | Crossfade |
| Horror | Cold dread, ambient drone | Glitch + radial |
| Sci-Fi | Neon cyan, synth, wonder | Radial reveal |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                           │
│  ┌─────────────────┐  ┌──────────────┐  ┌────────────────────┐ │
│  │   React App     │  │  Web Audio   │  │  WebSocket Client  │ │
│  │                 │  │  Capture     │  │                    │ │
│  │ • VideoPlayer   │  │ • PCM16      │  │ • Intent receiver  │ │
│  │ • WebGL canvas  │  │   16kHz mono │  │ • Reconnect logic  │ │
│  │ • GenreOverlay  │  │ • Mic stream │  │                    │ │
│  │ • Commentary    │  │              │  │                    │ │
│  └────────┬────────┘  └──────┬───────┘  └────────┬───────────┘ │
└───────────┼──────────────────┼───────────────────┼─────────────┘
            └──────────────────┴───────────────────┘
                                       │ PCM audio bytes (WebSocket)
                                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                     GEMINI LIVE API LAYER                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  gemini-2.0-flash-live-001                              │   │
│  │  • Real-time speech-to-intent (<500ms)                  │   │
│  │  • Cinematic intent system prompt                       │   │
│  │  • Structured JSON output                               │   │
│  │    {genre, action, confidence, emotional_intensity}     │   │
│  └─────────────────────────┬───────────────────────────────┘   │
└────────────────────────────┼────────────────────────────────────┘
                             │ intent JSON
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ORCHESTRATION ENGINE (Cloud Run)               │
│  ┌───────────────┐  ┌───────────────┐  ┌──────────────────────┐ │
│  │  Narrative    │  │    Scene      │  │   Audio              │ │
│  │  State        │  │  Conductor    │  │   Crossfader         │ │
│  │  Machine      │  │               │  │                      │ │
│  │               │  │ • Intent →    │  │ • Stem transition    │ │
│  │ • Coherence   │  │   segment     │  │   plan (bass/drums/  │ │
│  │   guardrails  │  │ • Genre       │  │   melody/ambient)    │ │
│  │ • Conflict    │  │   adjacency   │  │ • Equal-power        │ │
│  │   detection   │  │ • Preload     │  │   envelopes          │ │
│  │ • History     │  │   hints       │  │                      │ │
│  └───────────────┘  └───────┬───────┘  └──────────────────────┘ │
└───────────────────────────┬─┴────────────────────────────────────┘
                            │ scene descriptor + audio transition plan
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PRE-GENERATED ASSET LIBRARY                    │
│         Google Cloud Storage + CDN (us-central1)                │
│                                                                 │
│   NOIR          ROM-COM        HORROR         SCI-FI            │
│  ┌──┬──┬──┐    ┌──┬──┬──┐    ┌──┬──┬──┐    ┌──┬──┬──┐        │
│  │Op│Cn│Cl│    │Op│Cn│Cl│    │Op│Cn│Cl│    │Op│Cn│Cl│        │
│  │8s│8s│8s│    │8s│8s│8s│    │8s│8s│8s│    │8s│8s│8s│        │
│  └──┴──┴──┘    └──┴──┴──┘    └──┴──┴──┘    └──┴──┴──┘        │
│                                                                 │
│  Op=Opening  Cn=Confrontation  Cl=Climax                       │
│  Generated via: Veo 3.0 on Vertex AI (batch)                   │
│  Metadata: scene_graph.json · emotional_valence.json           │
└─────────────────────────────────────────────────────────────────┘

WebGL Transition Engine (browser-side):
  Crossfade ──── Noir ↔ Rom-Com
  Glitch    ──── Noir ↔ Horror · Rom-Com ↔ Horror
  Radial    ──── Noir ↔ Sci-Fi · Horror ↔ Sci-Fi
  Wipe      ──── Rom-Com ↔ Sci-Fi
```

**Latency budget:** voice → visual change ≤ 800ms

---

## Project Structure

```
infinite-canvas/
├── frontend/               # React 18 app
│   ├── src/
│   │   ├── components/     # VideoPlayer, VoiceController, GenreOverlay, DirectorCommentary
│   │   ├── hooks/          # useSceneState, useGeminiLive
│   │   └── utils/          # WebGL transition engine (4 shader types)
│   └── Dockerfile
├── backend/                # FastAPI orchestration server
│   ├── main.py             # App entrypoint + WebSocket voice endpoint
│   ├── gemini/             # Gemini Live API client
│   ├── orchestration/      # Scene conductor, state machine, audio crossfader
│   ├── api/                # REST routes
│   └── Dockerfile
├── assets/
│   ├── video/              # 12 pre-generated MP4 segments (place here or GCS)
│   ├── audio/              # 16 stem files (4 genres × 4 stems)
│   └── metadata/           # scene_graph.json, emotional_valence.json
├── scripts/
│   └── generate_assets.py  # Veo 3.0 batch generation pipeline
├── infrastructure/         # Terraform (Cloud Run, GCS, CDN, Secret Manager)
└── docker-compose.yml
```

---

## Quick Start (Local)

### Prerequisites
- Node 20+, Python 3.11+, Docker (optional)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com)

### 1. Backend

```bash
cd backend
cp .env.example .env
# Edit .env: set GEMINI_API_KEY=your_key
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm start
# Opens http://localhost:3000
```

### 3. Docker Compose (full stack)

```bash
cp backend/.env.example .env
# Edit .env: set GEMINI_API_KEY
docker-compose up --build
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

---

## Generate Video Assets (Veo 3.0)

```bash
# Dry run — print all 12 prompts without generating
python scripts/generate_assets.py --dry-run

# Full generation (requires GCP project with Vertex AI enabled)
python scripts/generate_assets.py \
  --project your-gcp-project \
  --bucket your-gcs-bucket \
  --concurrency 3
```

The script generates all 12 segments with locked **visual anchors** (identical camera angle, actor positions, object placement) enabling seamless WebGL transitions.

---

## Deploy to GCP

```bash
cd infrastructure

# Initialize Terraform
terraform init

# Plan deployment
terraform plan \
  -var="project_id=your-project" \
  -var="gemini_api_key=your-key"

# Apply
terraform apply \
  -var="project_id=your-project" \
  -var="gemini_api_key=your-key"
```

Resources created: Cloud Run (orchestrator), Cloud Storage (assets), Cloud CDN, Artifact Registry, Secret Manager, Cloud Monitoring alert.

---

## How Voice Control Works

1. Browser captures microphone audio (PCM16, 16kHz)
2. Streams audio bytes over WebSocket to backend
3. Backend forwards to **Gemini Live API** (`gemini-2.0-flash-live-001`)
4. Gemini parses speech → structured intent JSON in real-time:
   ```json
   {"genre": "horror", "action": "change_genre", "confidence": 0.92, "emotional_intensity": 0.8}
   ```
5. **NarrativeStateMachine** validates against current story state
6. **SceneConductor** resolves the target video segment + audio transition plan
7. Client performs WebGL crossfade + Web Audio stem crossfade simultaneously

---

## Voice Commands

| Say | Effect |
|-----|--------|
| "make it noir" | Switch to noir genre |
| "romantic" / "make it a rom-com" | Switch to rom-com |
| "she's the villain" / "horror" | Switch to horror |
| "cyberpunk" / "sci-fi" / "future" | Switch to sci-fi |
| "next scene" | Advance to next narrative beat |
| "reset" | Return to opening noir scene |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + WebGL (custom GLSL shaders) |
| Voice Pipeline | Gemini Live API (`gemini-2.0-flash-live-001`) |
| Backend | FastAPI + Python 3.11 |
| Video Generation | Veo 3.0 (Vertex AI) |
| Storage | Google Cloud Storage |
| Compute | Cloud Run (auto-scaling) |
| Audio | Stem crossfading (scipy envelopes) + Web Audio API |
| Infrastructure | Terraform |

---

## Director's Commentary

After the 3-beat experience ends, the AI generates a personalized retrospective:
- Your unique narrative path through the possibility space
- Genre distribution (e.g. "You preferred horror 60% of the time")
- A personality read based on your choices

---

*We didn't build a video player. We built a reality conductor.*

`#GeminiLiveAgentChallenge`
