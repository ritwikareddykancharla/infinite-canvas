# System Architecture

## Overview

InfiniteCanvas is a four-layer system: a React browser client, a FastAPI orchestration backend running on Cloud Run, a Gemini Live API session for real-time speech processing, and a pre-generated asset library on Google Cloud Storage with CDN.

The fundamental design principle is **latency above all else.** Every architectural decision traces back to the 800ms voice-to-visual-change budget.

---

## Full System Diagram

```
┌───────────────────────────────────────────────────────────────────────────┐
│                              BROWSER (CLIENT)                             │
│                                                                           │
│  ┌─────────────────┐   ┌────────────────────┐   ┌──────────────────────┐ │
│  │  React App      │   │  Web Audio API     │   │  WebSocket Client    │ │
│  │                 │   │                    │   │                      │ │
│  │  VideoPlayer    │   │  getUserMedia()    │   │  PCM16 audio stream  │ │
│  │  ├ WebGL canvas │   │  AudioWorklet      │   │  Intent receiver     │ │
│  │  └ dual <video> │   │  PCM16 @ 16kHz     │   │  Reconnect + backoff │ │
│  │                 │   │  mono, no compress │   │                      │ │
│  │  GenreOverlay   │   └────────┬───────────┘   └──────────┬───────────┘ │
│  │  VoiceCtrl      │            │ raw PCM bytes              │ JSON events │
│  │  Commentary     │            └────────────────────────────┘            │
│  └────────┬────────┘                          │ WebSocket /ws/voice        │
└───────────┼──────────────────────────────────┼────────────────────────────┘
            │ video URL + transition params     │ audio bytes up / intents down
            ▼                                  ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND  (Cloud Run, us-central1)              │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  WebSocket Handler  /ws/voice                                        │ │
│  │                                                                      │ │
│  │  per-connection:                                                     │ │
│  │    GeminiLiveClient  ──► Gemini Live API  ──► _recv_loop()           │ │
│  │    NarrativeStateMachine                                             │ │
│  │    SceneConductor                                                    │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  REST API  /api/*                                                    │ │
│  │                                                                      │ │
│  │  POST /intent          manual intent injection (test / fallback)     │ │
│  │  GET  /scenes          list all 12 scene segments                    │ │
│  │  POST /preload-hints   prefetch URLs for next likely transitions     │ │
│  │  GET  /audio-transition stem crossfade plan                          │ │
│  │  POST /commentary      ADK-powered director's commentary             │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │  ADK Layer  backend/adk/                                             │ │
│  │                                                                      │ │
│  │  LlmAgent  infinite_canvas_conductor                                 │ │
│  │    ├ FunctionTool: change_scene                                      │ │
│  │    ├ FunctionTool: get_available_genres                              │ │
│  │    └ FunctionTool: generate_director_commentary                      │ │
│  │                                                                      │ │
│  │  MCP Server  (stdio / SSE)                                           │ │
│  │    └ exposes same 3 tools over Model Context Protocol                │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
              ┌─────────────────┴──────────────────┐
              ▼                                    ▼
┌─────────────────────────┐          ┌─────────────────────────────────────┐
│  GEMINI LIVE API        │          │  GOOGLE CLOUD STORAGE + CDN         │
│                         │          │                                     │
│  gemini-2.0-flash-      │          │  12 × MP4 video segments            │
│  live-001               │          │  4 genres × 3 beats × ~8s           │
│                         │          │  generated via Veo 3.0              │
│  PCM16 audio in →       │          │                                     │
│  intent JSON out        │          │  16 × WAV audio stems               │
│  <500ms latency         │          │  4 genres × 4 stems                 │
│                         │          │  (bass, drums, melody, ambient)     │
│  System prompt:         │          │                                     │
│  cinematic intent       │          │  CDN edge cache → <100ms delivery   │
│  parser                 │          │                                     │
└─────────────────────────┘          └─────────────────────────────────────┘
```

---

## Latency Budget Breakdown

The 800ms total budget is distributed across three phases:

| Phase | Target | How Achieved |
|-------|--------|--------------|
| Speech → Intent | ≤ 500ms | Gemini Live API streaming session (no HTTP round-trips) |
| Intent → Scene URL | ≤ 100ms | In-memory state machine + O(1) scene graph lookup |
| URL → First Frame | ≤ 200ms | CDN-cached assets + preload hints start client fetch early |

The WebGL transition shader fires on the client **before** the new video is fully buffered — using a glitch/blur frame to cover any remaining load time. The viewer perceives an instant response even when the network is slow.

---

## Asset Library Design

### The Visual Anchor Problem

The central technical challenge of the pre-generation approach is *visual consistency across genres*. If the two actors are in different positions between the noir and rom-com versions of the same scene, any WebGL crossfade will produce a jarring spatial discontinuity.

Every Veo 3.0 generation prompt includes a locked **visual anchor spec**:

```
LOCKED ANCHORS (do not vary):
- Camera: medium two-shot, lens 35mm, slight low angle
- Actor A: left of frame, facing right, hands on table
- Actor B: right of frame, facing left, leaning back
- Key object: manila envelope on table centre
- Room geometry: rectangular, single door frame right
```

Only these elements vary between genres:

| Element | Noir | Rom-Com | Horror | Sci-Fi |
|---------|------|---------|--------|--------|
| Colour grade | Blue-silver, deep shadow | Warm amber, soft fill | Cold desaturated, green tint | Neon cyan, volumetric |
| Lighting | Hard shadows, venetian blinds | Soft diffused, golden hour | Practical only, flickering | LED strip, backlit |
| Score stems | Jazz piano, upright bass | Acoustic guitar, strings | Drone pad, dissonance | Synth arp, digital perc |
| Emotional valence | Suspicion, weight | Longing, warmth | Dread, unease | Wonder, anticipation |

### Segment Naming Convention

```
{genre}_{beat}.mp4

noir_opening.mp4          romcom_opening.mp4
noir_confrontation.mp4    romcom_confrontation.mp4
noir_climax.mp4           romcom_climax.mp4
horror_opening.mp4        scifi_opening.mp4
horror_confrontation.mp4  scifi_confrontation.mp4
horror_climax.mp4         scifi_climax.mp4
```

12 segments total. Each ~8 seconds. Total asset size: ~240MB uncompressed, ~80MB at H.264 target bitrate.

---

## WebGL Transition Engine

All transitions run on the GPU via GLSL fragment shaders. Two `<video>` elements are always maintained — one playing, one preloading — and the shader crossfades between them using a `progress` uniform animated at 60fps.

### Transition Types by Genre Pair

```
Noir    ↔ Rom-Com   →  CROSSFADE   (smooth dissolve, no distortion)
Noir    ↔ Horror    →  GLITCH      (RGB channel split + horizontal tears)
Noir    ↔ Sci-Fi    →  RADIAL      (iris-in reveal from screen centre)
Rom-Com ↔ Horror    →  GLITCH      (most jarring — maximum narrative distance)
Rom-Com ↔ Sci-Fi    →  WIPE        (diagonal wipe, light to luminous)
Horror  ↔ Sci-Fi    →  RADIAL      (escape from darkness into light)
```

Genre distance determines which transition fires — not a hard-coded table, but computed from the `GENRE_DISTANCES` semantic matrix in `scene_conductor.py`.

---

## Narrative State Machine

The state machine sits between the Gemini intent parser and the scene resolver. Its job is to prevent cinematically incoherent state sequences.

### State Transitions

```
Initial state: {genre: "noir", beat: 0, committed: {}}

change_genre("romcom")  →  {genre: "romcom", beat: 0, committed: {lovers_committed}}
change_genre("horror")  →  REJECTED — "lovers_committed" blocks horror
change_genre("scifi")   →  {genre: "scifi", beat: 0, committed: {lovers_committed}}

--- (reset) ---

change_genre("horror")  →  {genre: "horror", beat: 0, committed: {villain_committed}}
change_genre("romcom")  →  REJECTED — "villain_committed" blocks romcom
next_beat()             →  {genre: "horror", beat: 1, committed: {villain_committed}}
```

### Committed States Reference

| Lock | Set By | Blocks |
|------|--------|--------|
| `villain_committed` | horror | romcom |
| `lovers_committed` | romcom | horror |
| `hero_dead_committed` | (future) | romcom, scifi |

---

## Cloud Infrastructure

All infrastructure is defined in Terraform (`infrastructure/`).

```
Google Cloud Project
├── Cloud Run (backend)
│   ├── Auto-scaling: 0 → 10 instances
│   ├── Memory: 512Mi
│   ├── Concurrency: 80
│   └── Health check: GET /health
│
├── Cloud Storage (assets)
│   ├── Bucket: {project}-infinite-canvas-assets
│   ├── Location: us-central1
│   └── CDN: enabled via Cloud CDN backend bucket
│
├── Artifact Registry
│   └── Docker images: backend, frontend
│
└── Secret Manager
    └── GEMINI_API_KEY (version 1)
```

---

## Data Flow: One Voice Command, End to End

```
1. Viewer says "make it horror"

2. Browser AudioWorklet captures PCM16 frames (16kHz, mono)
   → packed into ArrayBuffer
   → sent over WebSocket as binary message

3. Backend WebSocket handler receives bytes
   → GeminiLiveClient.send_audio(bytes)
   → forwarded to Gemini Live session (streaming, no HTTP overhead)

4. Gemini Live processes audio stream
   → VAD detects end of utterance
   → LLM generates JSON response:
     {"genre": "horror", "action": "change_genre", "confidence": 0.92, "emotional_intensity": 0.85}
   → _recv_loop() receives text chunk
   → _parse_intent() validates JSON, confidence threshold ≥ 0.5

5. _handle_intent() called with raw_intent
   → NarrativeStateMachine.validate_intent(intent)
     → checks villain_committed, lovers_committed, etc.
     → returns validated intent (or None if rejected)
   → SceneConductor.resolve(validated)
     → maps genre+beat → scene key "horror_opening"
     → returns {video_url, audio_stems, transition_duration_ms, ...}
   → NarrativeStateMachine.apply(validated)
     → sets villain_committed in state

6. Backend sends JSON over WebSocket:
   {
     "type": "intent",
     "intent": {
       "genre": "horror",
       "action": "change_genre",
       "scene": {
         "video_url": "/assets/video/horror_opening.mp4",
         "audio_stems": [...],
         "transition_duration_ms": 380
       }
     }
   }

7. Frontend useGeminiLive hook receives message
   → dispatches to useSceneState
   → VideoPlayer starts loading horror_opening.mp4 into inactive <video> ref
   → WebGL shader begins transition animation (progress 0 → 1 over 380ms)
   → Web Audio API crossfades stem mix:
       noir stems fade out, horror stems fade in

8. Viewer sees and hears the genre change
   Total elapsed: ~650ms from end of speech
```
