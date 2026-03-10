# Backend Deep Dive

## Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| FastAPI | 0.115.5 | Async web framework, WebSocket support |
| Python | 3.11 | Runtime |
| google-genai | 0.8.0 | Gemini Live API client |
| google-adk | ≥1.0.0 | Agent Development Kit orchestration |
| uvicorn | 0.32.1 | ASGI server |
| scipy / numpy | latest | Equal-power audio envelope calculation |
| pydantic | 2.10.1 | Request validation |

---

## Directory Structure

```
backend/
├── main.py                        # App entry point, WebSocket handler
├── gemini/
│   └── live_client.py             # Gemini Live API session wrapper
├── orchestration/
│   ├── scene_conductor.py         # Intent → video segment resolver
│   ├── state_machine.py           # Narrative coherence guardrails
│   └── audio_crossfader.py        # Stem-level transition planner
├── adk/
│   ├── __init__.py
│   ├── agent.py                   # ADK LlmAgent with scene tools
│   └── mcp_server.py              # MCP server (stdio + SSE transports)
├── api/
│   └── routes.py                  # REST API routes
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## main.py — Entry Point

FastAPI app with lifespan context manager, CORS middleware, and the primary WebSocket endpoint.

### Lifespan

```python
@asynccontextmanager
async def lifespan(app):
    app.state.scene_graph = _load_scene_graph()   # Load metadata once at startup
    app.state.active_sessions = {}
    yield
```

The scene graph JSON is loaded once at startup and stored on `app.state` — shared across all requests with no per-request I/O.

### WebSocket Handler `/ws/voice`

Each WebSocket connection gets its own isolated set of objects:

```
WebSocket connection
├── GeminiLiveClient    — own Gemini Live session
├── SceneConductor      — own instance (stateless, safe to share but isolated for clarity)
└── NarrativeStateMachine — own narrative state (each viewer's story is independent)
```

This is important: two simultaneous viewers have completely separate narrative states. There is no global story state.

```python
async for message in websocket.iter_bytes():
    await gemini_client.send_audio(message)
```

The handler loop is minimal by design. All logic is in `_handle_intent()`, called asynchronously from the Gemini recv loop via `asyncio.create_task()`.

---

## gemini/live_client.py — Gemini Live API

### Session Lifecycle

```
GeminiLiveClient.start()
  → genai.Client(api_key)
  → client.aio.live.connect(model, config).__aenter__()
     config:
       response_modalities: ["TEXT"]
       system_instruction: SYSTEM_PROMPT
       speech_config: VAD enabled
  → asyncio.create_task(_recv_loop())

_recv_loop():
  async for response in session.receive():
    if response.text:
      intent = _parse_intent(response.text)
      if intent: on_intent(intent)

send_audio(pcm_bytes):
  session.send(LiveClientRealtimeInput(
    media_chunks=[Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")]
  ))
```

### System Prompt Design

The system prompt is engineered specifically for the cinematic intent parsing task:

```
You are the InfiniteCanvas Reality Conductor — an AI that understands cinematic intent.

Parse voice commands → JSON with: {genre, action, confidence, emotional_intensity, feedback}

genre:              "noir|romcom|horror|scifi|null"
action:             "change_genre|next_beat|reset|null"
confidence:         0.0–1.0 (how certain you are of the intent)
emotional_intensity: 0.0–1.0 (how urgent/strong the viewer's desire for change is)
feedback:           optional short response to read back to viewer

Only respond with the JSON. No other text.
```

The `emotional_intensity` field drives transition speed on the frontend. High intensity → faster, more jarring transition. Low intensity → slow dissolve.

### Mock Mode

If `GEMINI_API_KEY` is not set (development without a key), the client runs in mock mode: a silent loop that never fires intents. The REST `POST /api/intent` endpoint is available as a manual alternative during testing.

### Fallback Chain

```
1. Try Gemini Live API → start session
2. If ImportError or connection failure → _mock_recv_loop()
3. Intent can still be injected via REST /api/intent
```

---

## orchestration/scene_conductor.py — Intent Resolver

### Genre Distance Matrix

The conductor uses a semantic distance matrix to resolve ambiguous genre references and select transition types:

```python
GENRE_DISTANCES = {
    ("noir", "romcom"):  0.7,   # Far — different emotional polarity
    ("noir", "horror"):  0.3,   # Close — both dark, shadow-adjacent
    ("noir", "scifi"):   0.5,   # Medium — both cerebral/isolated
    ("romcom", "horror"): 0.9,  # Very far — maximum contrast
    ("romcom", "scifi"): 0.6,   # Medium-far — both optimistic, different textures
    ("horror", "scifi"): 0.4,   # Medium-close — both uncanny
}
```

Distance < 0.4 → crossfade
Distance 0.4–0.6 → radial
Distance 0.6–0.8 → wipe
Distance > 0.8 → glitch

### Scene Resolution

```python
def resolve(self, intent: dict) -> dict:
    genre = intent.get("genre") or "noir"
    beat_index = intent.get("beat_index", 0)
    beat_name = BEATS[min(beat_index, 2)]
    scene_key = f"{genre}_{beat_name}"
    meta = self.scene_graph.get(scene_key, {})
    return {
        "genre": genre,
        "beat": beat_name,
        "video_url": meta.get("video_url", f"/assets/video/{scene_key}.mp4"),
        "audio_stems": meta.get("audio_stems", []),
        "transition_duration_ms": self._calc_transition_duration(
            intent.get("emotional_intensity", 0.5)
        ),
    }
```

### Preload Hints

The conductor also generates preload hints — URLs to fetch in advance for the most likely next transitions:

```python
def get_preload_hints(self, current_genre, beat_index):
    next_beat = min(beat_index + 1, 2)
    hints = [
        f"/assets/video/{current_genre}_{BEATS[next_beat]}.mp4",   # same genre, next beat
        f"/assets/video/{closest_genre}_{BEATS[beat_index]}.mp4",  # closest genre, same beat
    ]
    return hints
```

The frontend calls `POST /api/preload-hints` after each transition and preloads the returned URLs with `<link rel="preload">` tags — hiding network latency for the most common next transitions.

---

## orchestration/state_machine.py — Narrative Coherence

### Design Philosophy

The state machine is not a permission system — it is a *story collaborator*. Its job is to prevent the viewer from accidentally creating an incoherent narrative, not to limit their freedom.

When a transition is blocked, the machine provides a natural-language conflict message that Gemini can optionally speak back to the viewer:

```
"That would conflict with the established darkness. Try horror or noir instead?"
"That would undo the connection they just made. Try noir or sci-fi instead?"
```

### State Object

```python
@dataclass
class NarrativeState:
    current_genre: str = "noir"
    current_beat: int = 0
    committed_states: set = field(default_factory=set)
    history: list = field(default_factory=list)
```

`history` is the ordered list of `{genre, beat}` dicts that feeds the Director's Commentary.

### Conflict Detection

```python
INCOMPATIBLE = {
    "villain_committed": {"romcom"},          # Can't fall in love after choosing villain
    "lovers_committed": {"horror"},           # Can't introduce dread after choosing love
    "hero_dead_committed": {"romcom", "scifi"}, # Reserved for future beats
}
```

---

## orchestration/audio_crossfader.py — Stem Transitions

### Stem Architecture

Each genre has 4 audio stems: `bass`, `drums`, `melody`, `ambient`.

Genre-specific prominence weights determine which stems are loud in which genre:

```python
STEM_WEIGHTS = {
    "noir":   {"bass": 0.9, "drums": 0.4, "melody": 0.8, "ambient": 0.3},
    "romcom": {"bass": 0.3, "drums": 0.5, "melody": 1.0, "ambient": 0.4},
    "horror": {"bass": 0.2, "drums": 0.1, "melody": 0.0, "ambient": 1.0},
    "scifi":  {"bass": 0.5, "drums": 0.7, "melody": 0.6, "ambient": 0.8},
}
```

Horror is notably all ambient, no melody — consistent with the genre's aural texture.

### Equal-Power Crossfade

The crossfader uses equal-power (constant-power) envelopes calculated via scipy to avoid the volume dip that occurs with linear crossfades:

```python
# Equal-power: sum of squares = 1 at all points
fade_out = np.cos(np.linspace(0, np.pi/2, steps))
fade_in  = np.sin(np.linspace(0, np.pi/2, steps))
```

The response from `GET /api/audio-transition` is a JSON plan with per-stem envelope arrays that the Web Audio API's `GainNode.setValueCurveAtTime()` can consume directly.

---

## api/routes.py — REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/intent` | Manual intent injection (testing / WebSocket fallback) |
| `GET` | `/api/scenes` | List all 12 scene segments |
| `POST` | `/api/preload-hints` | Get prefetch URLs for likely next transitions |
| `GET` | `/api/audio-transition` | Stem crossfade envelope plan |
| `POST` | `/api/commentary` | ADK-powered Director's Commentary |
| `GET` | `/api/scene-graph` | Full scene graph metadata |
| `GET` | `/health` | Health check (Cloud Run probe) |

### `/api/commentary`

The commentary endpoint layers two sources:

1. **Fast local computation** — genre distribution stats, dominant genre, personality read template. No LLM call. Always returns in <10ms.
2. **ADK enrichment** — if `google-adk` is installed and `GEMINI_API_KEY` is set, calls the ADK `LlmAgent` to generate a unique, LLM-authored analysis. Added as `adk_insight` in the response.

```python
# Fast fallback always runs first
base = generate_director_commentary(body.narrative_history)

# ADK enrichment — non-blocking, failure safe
try:
    adk_response = await run_agent(prompt, session_id=body.session_id)
    base["adk_insight"] = adk_response
except Exception:
    pass  # base commentary is always returned
```

This pattern means the endpoint degrades gracefully under all failure modes.
