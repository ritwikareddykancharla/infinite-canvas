# Frontend Deep Dive

## Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 18.3.1 | Component framework, concurrent rendering |
| Zustand (via hook) | 4.5.5 | Scene state management |
| WebGL / GLSL | native | GPU-accelerated video transitions |
| Web Audio API | native | Stem-based audio crossfading |
| WebSocket | native | Bidirectional audio/event channel to backend |
| nginx | 1.27 | Production static file server |

---

## Component Tree

```
App.jsx
├── VideoPlayer.jsx          # WebGL canvas + dual <video> + render loop
├── VoiceController.jsx      # Microphone permission + WebSocket connection
├── GenreOverlay.jsx         # Genre selector UI + beat progress + status bar
└── DirectorCommentary.jsx   # Post-experience personality summary
```

---

## App.jsx — Orchestrator

`App.jsx` owns the top-level state and wires the components together.

**Key responsibilities:**
- Initialises `useSceneState` (current genre, beat, transition flag, history)
- Initialises `useGeminiLive` (WebSocket lifecycle, audio capture)
- Handles `onSpeechIntent` events from the Gemini Live hook — applies scene changes
- Handles `onExperienceComplete` when beat 2 (climax) ends — shows Director's Commentary
- Passes scene URLs and transition params down to VideoPlayer

```jsx
// Core event handler
function handleSpeechIntent(intent) {
  if (intent.action === 'change_genre' && intent.scene) {
    applyGenreChange(intent.genre, intent.scene);
  } else if (intent.action === 'next_beat') {
    advanceBeat();
  } else if (intent.action === 'reset') {
    resetNarrative();
  }
}
```

---

## VideoPlayer.jsx — WebGL Renderer

The VideoPlayer maintains two `<video>` HTML elements — **active** (currently playing) and **inactive** (preloading the next segment). When a transition fires, the roles swap.

### WebGL Render Loop

```
requestAnimationFrame loop:
  1. Upload active video frame as texture0
  2. Upload inactive video frame as texture1
  3. Set progress uniform (0.0 → 1.0 over transition_duration_ms)
  4. Set transition_type uniform (0=crossfade, 1=wipe, 2=glitch, 3=radial)
  5. Draw fullscreen quad
  6. When progress >= 1.0: swap active/inactive refs, stop transition
```

The canvas is always 1920×1080 internally and scaled via CSS — no re-init needed on window resize.

### Transition Type Selection

The frontend receives a `transition_type` string from the backend scene descriptor. The mapping:

```js
const TRANSITION_IDS = {
  crossfade: 0,
  wipe:      1,
  glitch:    2,
  radial:    3,
};
```

---

## webgl-transitions.js — GLSL Shaders

Four custom fragment shaders implement the genre transitions. All share the same vertex shader (a fullscreen quad).

### Crossfade (Noir ↔ Rom-Com)

Simple alpha blend. The smoothest transition, appropriate for the smallest genre distance.

```glsl
void main() {
  vec4 a = texture2D(tex0, vUv);
  vec4 b = texture2D(tex1, vUv);
  gl_FragColor = mix(a, b, progress);
}
```

### Wipe (Rom-Com ↔ Sci-Fi)

Diagonal wipe from top-left to bottom-right. Creates a sense of spatial movement.

```glsl
void main() {
  float d = (vUv.x + vUv.y) * 0.5;
  float edge = smoothstep(progress - 0.05, progress + 0.05, d);
  gl_FragColor = mix(texture2D(tex0, vUv), texture2D(tex1, vUv), edge);
}
```

### Glitch (Noir ↔ Horror, Rom-Com ↔ Horror)

RGB channel split + horizontal scanline displacement. The most violent transition, reserved for the largest genre distance (rom-com to horror).

```glsl
void main() {
  float t = progress;
  float noise = fract(sin(vUv.y * 127.1 + t * 311.7) * 43758.5);
  vec2 offset = vec2(noise * 0.04 * t, 0.0);

  float r = texture2D(tex1, vUv + offset).r;
  float g = texture2D(tex1, vUv).g;
  float b = texture2D(tex1, vUv - offset).b;

  vec4 glitched = vec4(r, g, b, 1.0);
  gl_FragColor = mix(texture2D(tex0, vUv), glitched, t);
}
```

### Radial (Noir ↔ Sci-Fi, Horror ↔ Sci-Fi)

Iris-in from screen centre. Symbolises expanding possibility — escaping the enclosed world of noir/horror into the open space of science fiction.

```glsl
void main() {
  vec2 centre = vUv - 0.5;
  float dist = length(centre);
  float radius = progress * 0.8;
  float edge = smoothstep(radius, radius + 0.05, dist);
  gl_FragColor = mix(texture2D(tex1, vUv), texture2D(tex0, vUv), edge);
}
```

---

## useGeminiLive.js — WebSocket + Audio Capture

This hook manages the complete voice pipeline on the client side.

### Audio Capture

```
getUserMedia({ audio: true })
  → AudioContext (16kHz sample rate)
  → MediaStreamSource
  → AudioWorkletNode (pcm-processor)
    → converts Float32 → Int16
    → posts ArrayBuffer to main thread
  → WebSocket.send(pcmBuffer)
```

The AudioWorklet runs in a dedicated thread to avoid blocking the UI or video rendering. Packets are sent as fast as they arrive — the Gemini Live session handles buffering.

### WebSocket Lifecycle

```
connect()
  → new WebSocket(wsUrl)
  → onopen: start audio capture
  → onmessage: parse JSON, call onIntent callback
  → onclose / onerror: exponential backoff reconnect
    (delays: 1s, 2s, 4s, 8s, 16s, then give up)
```

The reconnection logic is essential for production: mobile devices lose network briefly, users tab away, Cloud Run instances restart. The experience must survive these interruptions transparently.

### Intent Message Format

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
      "beat": "opening",
      "beat_index": 0,
      "video_url": "/assets/video/horror_opening.mp4",
      "audio_stems": ["horror_bass", "horror_ambient"],
      "emotional_valence": -0.7,
      "transition_duration_ms": 380
    }
  }
}
```

---

## useSceneState.js — Narrative State

Client-side mirror of the backend narrative state. Tracks:

```js
{
  currentGenre: "noir",         // active genre
  currentBeat: 0,               // 0=opening, 1=confrontation, 2=climax
  isTransitioning: false,       // true during WebGL transition
  narrativeHistory: [],         // [{genre, beat}, ...] for Director's Commentary
}
```

The client state is informational only — the authoritative state lives in the backend `NarrativeStateMachine`. The client state drives UI (genre indicator, beat progress dots, transition lock) and accumulates history for the commentary endpoint.

---

## GenreOverlay.jsx — Control UI

The overlay sits above the WebGL canvas (CSS `position: absolute; z-index: 10`).

**Elements:**
- 4 genre buttons (top row) — clickable as alternative to voice
- 3 beat progress dots (centre) — filled as story advances
- Listening indicator — animated when microphone is active
- Status bar — displays current Gemini feedback or conflict messages

The overlay fades to 20% opacity when a video is playing to avoid competing with the cinematic experience, and returns to full opacity on hover or speech detection.

---

## DirectorCommentary.jsx — Post-Experience

Shown after beat 2 (climax) ends. Calls `POST /api/commentary` with the full `narrativeHistory` array.

**Displays:**
- Dominant genre badge
- Personality read (one sentence)
- Genre distribution bar chart (pure CSS, no chart library)
- Narrative arc timeline — genre badges in sequence order
- ADK insight (if available) — longer, LLM-generated analysis

The component has a 1.5s entrance animation (fade + slide up) to give a cinematic quality to the reveal.

---

## Production Build

The frontend Dockerfile uses a two-stage build:

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build          # Vite production build → /app/dist

# Stage 2: Serve
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

The nginx config handles:
- SPA routing (all routes → `index.html`)
- Gzip compression for JS/CSS
- Cache headers for static assets (1 year for hashed filenames, no-cache for `index.html`)
- WebSocket proxy to backend (when deployed together)
