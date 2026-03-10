# Google ADK & MCP Integration

## Overview

InfiniteCanvas uses Google Agent Development Kit (ADK) in two ways:

1. **ADK LlmAgent** (`backend/adk/agent.py`) — an orchestration agent with scene control tools, used by the `POST /api/commentary` endpoint to generate rich, LLM-authored Director's Commentary.

2. **MCP Server** (`backend/adk/mcp_server.py`) — a standalone Model Context Protocol server that exposes the same scene tools over stdio or SSE transport, enabling any MCP client (Claude Code, another ADK agent's `McpToolset`, custom tooling) to control the liquid movie.

---

## ADK Agent

### Agent Identity

```python
LlmAgent(
    name="infinite_canvas_conductor",
    model="gemini-2.0-flash",          # configurable via GEMINI_MODEL env var
    description="InfiniteCanvas Reality Conductor — cinematic scene orchestration",
    instruction=AGENT_INSTRUCTION,
    tools=[
        FunctionTool(change_scene),
        FunctionTool(get_available_genres),
        FunctionTool(generate_director_commentary),
    ],
)
```

### Tools

#### `change_scene(genre, beat_index=0)`

Resolves which video segment to serve for a given genre and beat.

```python
# Input
change_scene(genre="horror", beat_index=1)

# Output
{
    "genre": "horror",
    "beat": "confrontation",
    "beat_index": 1,
    "video_url": "/assets/video/horror_confrontation.mp4",
    "status": "scene_changed"
}
```

#### `get_available_genres()`

Returns all genres and beats with cinematic descriptions. Useful for the agent to reason about valid options before calling `change_scene`.

```python
{
    "genres": {
        "noir": "Shadows, moral ambiguity, jazz undertones",
        "romcom": "Golden light, warmth, piano melodies",
        "horror": "Cold dread, ambient drone, darkness",
        "scifi": "Neon cyan, synth music, wonder and awe"
    },
    "beats": {
        "opening": "Establishing the scene and characters (beat_index=0)",
        "confrontation": "Rising tension and conflict (beat_index=1)",
        "climax": "Peak emotional moment (beat_index=2)"
    }
}
```

#### `generate_director_commentary(narrative_history)`

Analyses a viewer's ordered list of scene choices and returns a personality read.

```python
# Input
generate_director_commentary([
    {"genre": "noir", "beat": "opening"},
    {"genre": "horror", "beat": "confrontation"},
    {"genre": "horror", "beat": "climax"},
])

# Output
{
    "dominant_genre": "horror",
    "personality_read": "You embrace tension. A fearless explorer drawn to the edges of comfort and safety.",
    "genre_distribution": {"noir": 33, "horror": 67},
    "total_choices": 3,
    "narrative_arc": ["noir", "horror", "horror"]
}
```

### Running the Agent Programmatically

```python
from adk.agent import run_agent

# Async — returns the agent's text response
response = await run_agent(
    user_message="Analyse this viewing history and give a director's commentary: noir (opening), horror (confrontation), horror (climax)",
    session_id="viewer-abc-123"
)
print(response)
# → "The viewer began with ambiguity but committed to darkness — a classic arc toward irreversible consequence..."
```

The `run_agent` function initialises a fresh `InMemorySessionService` and `Runner` per call. Sessions are identified by `session_id` to allow multi-turn conversations within the same viewing session.

---

## MCP Server

### What It Exposes

The MCP server exposes the same three tools (`change_scene`, `get_available_genres`, `generate_director_commentary`) over the Model Context Protocol. Any MCP-compatible client can:

- Browse the tool list
- Call tools with typed arguments
- Receive structured JSON results

### Transport Options

#### stdio (default)

The server reads from stdin and writes to stdout. This is the standard mode for local development and Claude Code integration.

```bash
python backend/adk/mcp_server.py
# or
MCP_TRANSPORT=stdio python backend/adk/mcp_server.py
```

#### SSE (Server-Sent Events)

For remote deployment or connecting multiple clients simultaneously, use SSE transport:

```bash
MCP_TRANSPORT=sse MCP_PORT=8001 python backend/adk/mcp_server.py
# Server running at http://localhost:8001/sse
```

---

## Connecting MCP Clients

### Claude Code (CLI)

**stdio:**
```bash
claude mcp add --transport stdio infinite-canvas -- python backend/adk/mcp_server.py
```

**SSE (after starting the server):**
```bash
claude mcp add --transport sse infinite-canvas http://localhost:8001/sse
```

**Verify connection:**
```bash
claude mcp list
# infinite-canvas: stdio — 3 tools
```

Then within Claude Code, you can directly call:
```
Use the infinite-canvas change_scene tool to switch to scifi confrontation
```

### Project `.mcp.json`

For team environments, commit this to the repo root so all contributors get the MCP server automatically:

```json
{
  "mcpServers": {
    "infinite-canvas": {
      "type": "stdio",
      "command": "python",
      "args": ["backend/adk/mcp_server.py"],
      "env": {
        "GEMINI_API_KEY": "${GEMINI_API_KEY}"
      }
    }
  }
}
```

### Another ADK Agent (McpToolset)

An external ADK agent can consume InfiniteCanvas as a toolset via `McpToolset`:

```python
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, SseServerParams

# Connect to the InfiniteCanvas SSE MCP server
toolset = McpToolset(
    connection_params=SseServerParams(
        url="https://your-cloud-run-backend.run.app/mcp/sse"
    )
)

# Use in an agent
agent = LlmAgent(
    name="film_director_assistant",
    model="gemini-2.0-flash",
    tools=[toolset],
    instruction="Help the user direct their liquid movie experience."
)
```

### Curl / HTTP (SSE mode)

```bash
# Start SSE server
MCP_TRANSPORT=sse python backend/adk/mcp_server.py &

# List tools
curl http://localhost:8001/sse   # initiates SSE session

# Tools are discovered via MCP initialize/list_tools handshake
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *(required)* | Google AI / Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Model used by the ADK LlmAgent |
| `MCP_TRANSPORT` | `stdio` | `stdio` or `sse` |
| `MCP_PORT` | `8001` | Port for SSE transport |

---

## Hackathon Compliance

The ADK integration satisfies the Gemini Live Agent Challenge technical requirement:

> *"Agents must be built using either Google GenAI SDK OR ADK (Agent Development Kit)"*

InfiniteCanvas uses **both**:
- **Google GenAI SDK** (`google-genai`) for the Gemini Live real-time voice session
- **Google ADK** (`google-adk`) for the `LlmAgent`-based scene orchestration and Director's Commentary

The MCP server additionally demonstrates how the InfiniteCanvas experience can be composed into larger multi-agent workflows — an external orchestration agent could control the liquid movie as one tool among many, opening up possibilities like narrative generation, accessibility overlays, or multi-viewer synchronisation.
