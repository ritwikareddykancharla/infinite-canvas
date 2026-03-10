# API Reference

Base URL (local): `http://localhost:8000`
Base URL (production): `https://<cloud-run-service>.run.app`

---

## WebSocket

### `WS /ws/voice`

Primary real-time channel. Send raw PCM16 audio bytes up; receive structured intent events down.

**Connect:**
```js
const ws = new WebSocket('ws://localhost:8000/ws/voice');
```

**On open — server sends:**
```json
{ "type": "connected", "session_id": "140234567890" }
```

**Client → Server:**
Binary WebSocket frames containing raw PCM16 audio at 16kHz, mono.
No framing, no headers — raw bytes only.

**Server → Client:**

*Intent event (scene change):*
```json
{
  "type": "intent",
  "intent": {
    "genre": "horror",
    "action": "change_genre",
    "confidence": 0.92,
    "emotional_intensity": 0.85,
    "feedback": null,
    "scene": {
      "genre": "horror",
      "beat": "confrontation",
      "beat_index": 1,
      "video_url": "/assets/video/horror_confrontation.mp4",
      "audio_stems": [
        { "stem": "horror_ambient", "weight": 1.0 },
        { "stem": "horror_bass",    "weight": 0.2 }
      ],
      "emotional_valence": -0.75,
      "transition_duration_ms": 340
    }
  }
}
```

*Intent event (beat advance):*
```json
{
  "type": "intent",
  "intent": {
    "genre": null,
    "action": "next_beat",
    "confidence": 1.0,
    "emotional_intensity": 0.0,
    "scene": { ... }
  }
}
```

*Conflict event (rejected intent):*
```json
{
  "type": "intent",
  "intent": {
    "feedback": "That would conflict with the established darkness. Try horror or noir instead?"
  }
}
```

---

## REST API

### `POST /api/intent`

Manual intent injection — REST fallback for when WebSocket is unavailable (testing, CI, accessibility).

**Request:**
```json
{
  "genre": "scifi",
  "action": "change_genre",
  "confidence": 0.9,
  "emotional_intensity": 0.7,
  "beat_index": 0
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `genre` | string\|null | null | `noir\|romcom\|horror\|scifi` |
| `action` | string | `change_genre` | `change_genre\|next_beat\|reset` |
| `confidence` | float | 0.9 | 0.0–1.0 |
| `emotional_intensity` | float | 0.5 | 0.0–1.0, drives transition speed |
| `beat_index` | int | 0 | 0–2 |

**Response (ok):**
```json
{
  "status": "ok",
  "scene": {
    "genre": "scifi",
    "beat": "opening",
    "beat_index": 0,
    "video_url": "/assets/video/scifi_opening.mp4",
    "audio_stems": [...],
    "emotional_valence": 0.8,
    "transition_duration_ms": 500
  }
}
```

**Response (rejected):**
```json
{
  "status": "rejected",
  "feedback": "That would undo the connection they just made. Try noir or sci-fi instead?"
}
```

---

### `GET /api/scenes`

List all 12 pre-generated scene segments.

**Response:**
```json
{
  "scenes": [
    { "genre": "noir",   "beat": "opening",       "beat_index": 0, "video_url": "/assets/video/noir_opening.mp4" },
    { "genre": "noir",   "beat": "confrontation", "beat_index": 1, "video_url": "/assets/video/noir_confrontation.mp4" },
    { "genre": "noir",   "beat": "climax",        "beat_index": 2, "video_url": "/assets/video/noir_climax.mp4" },
    { "genre": "romcom", "beat": "opening",       "beat_index": 0, "video_url": "/assets/video/romcom_opening.mp4" },
    ...
  ],
  "total": 12
}
```

---

### `POST /api/preload-hints`

Returns URLs to prefetch for the most likely upcoming transitions.

**Request:**
```json
{ "current_genre": "noir", "beat_index": 0 }
```

**Response:**
```json
{
  "hints": [
    "/assets/video/noir_confrontation.mp4",
    "/assets/video/horror_opening.mp4"
  ]
}
```

The first hint is always same-genre next-beat. The second is the semantically closest genre at the current beat.

---

### `GET /api/audio-transition`

Returns a stem-level crossfade envelope plan for a genre switch.

**Query params:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `from_genre` | string | yes | Source genre |
| `to_genre` | string | yes | Target genre |
| `duration_ms` | int | no (800) | Crossfade duration |

**Example:**
```
GET /api/audio-transition?from_genre=noir&to_genre=horror&duration_ms=400
```

**Response:**
```json
{
  "from_genre": "noir",
  "to_genre": "horror",
  "duration_ms": 400,
  "steps": 40,
  "stems": {
    "bass":    { "fade_out": [1.0, 0.97, ...], "fade_in": [0.0, 0.03, ...] },
    "drums":   { "fade_out": [0.4, 0.38, ...], "fade_in": [0.1, 0.11, ...] },
    "melody":  { "fade_out": [0.8, 0.77, ...], "fade_in": [0.0, 0.0, ...] },
    "ambient": { "fade_out": [0.3, 0.28, ...], "fade_in": [1.0, 1.0, ...] }
  }
}
```

Envelope arrays use equal-power (constant-power) curves. Each array has `steps` values, where `steps = duration_ms / 10`. Use with `GainNode.setValueCurveAtTime()` in the Web Audio API.

---

### `POST /api/commentary`

Generate Director's Commentary for a completed viewing session.

**Request:**
```json
{
  "narrative_history": [
    { "genre": "noir",   "beat": "opening" },
    { "genre": "horror", "beat": "confrontation" },
    { "genre": "horror", "beat": "climax" }
  ],
  "session_id": "viewer-abc-123"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `narrative_history` | array | yes | Ordered `{genre, beat}` choices |
| `session_id` | string | no | Viewer session ID for ADK context |

**Response (base):**
```json
{
  "dominant_genre": "horror",
  "personality_read": "You embrace tension. A fearless explorer drawn to the edges of comfort and safety.",
  "genre_distribution": { "noir": 33, "horror": 67 },
  "total_choices": 3,
  "narrative_arc": ["noir", "horror", "horror"]
}
```

**Response (with ADK enrichment):**
```json
{
  "dominant_genre": "horror",
  "personality_read": "You embrace tension...",
  "genre_distribution": { "noir": 33, "horror": 67 },
  "total_choices": 3,
  "narrative_arc": ["noir", "horror", "horror"],
  "adk_insight": "This viewer began in ambiguity — noir's grey moral zone — before committing irreversibly to darkness. The pivot at the confrontation beat suggests they waited to see the characters' true natures before making a decisive directorial choice. A storyteller who rewards patience with consequence."
}
```

`adk_insight` is present only when `google-adk` is installed and `GEMINI_API_KEY` is set.

---

### `GET /api/scene-graph`

Returns the full scene graph metadata loaded from `assets/metadata/scene_graph.json`.

**Response:** (structure varies by scene)
```json
{
  "noir_opening": {
    "video_url": "https://storage.googleapis.com/.../noir_opening.mp4",
    "audio_stems": [...],
    "emotional_valence": -0.4,
    "visual_anchors": { "camera": "medium two-shot", ... },
    "transition_compatibility": { "romcom": "crossfade", "horror": "glitch", ... }
  },
  ...
}
```

---

### `GET /health`

Health check endpoint for Cloud Run readiness/liveness probes.

**Response:**
```json
{ "status": "ok", "service": "infinite-canvas-orchestrator" }
```

---

## Static Assets

Videos and audio stems are served as static files:

```
GET /assets/video/{genre}_{beat}.mp4
GET /assets/audio/{genre}_{stem}.wav
```

In production these are served directly from Google Cloud Storage via Cloud CDN — the backend `/assets/` mount is for local development only.
