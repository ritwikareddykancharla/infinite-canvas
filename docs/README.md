# InfiniteCanvas Documentation

> *We didn't build a video player. We built a reality conductor.*

Welcome to the InfiniteCanvas technical documentation. This folder contains the full design thesis, architecture deep-dives, and integration guides for the project submitted to the **Gemini Live Agent Challenge**.

---

## Contents

| File | Description |
|------|-------------|
| [thesis.md](./thesis.md) | The big idea — why InfiniteCanvas exists and what it means for interactive storytelling |
| [architecture.md](./architecture.md) | Full system architecture with diagrams — all layers from browser to Cloud Run |
| [frontend.md](./frontend.md) | React, WebGL shaders, Web Audio API, and the voice capture pipeline |
| [backend.md](./backend.md) | FastAPI, Gemini Live client, narrative state machine, scene conductor |
| [adk-mcp.md](./adk-mcp.md) | Google ADK agent and MCP server integration guide |
| [api-reference.md](./api-reference.md) | Complete REST API and WebSocket protocol reference |
| [deployment.md](./deployment.md) | Google Cloud deployment with Terraform — step by step |

---

## Quick Links

- **Run locally in 3 commands** → [deployment.md#local-development](./deployment.md#local-development)
- **Understand the voice pipeline** → [backend.md#gemini-live-client](./backend.md#gemini-live-client)
- **Connect via MCP** → [adk-mcp.md#connecting-mcp-clients](./adk-mcp.md#connecting-mcp-clients)
- **The hackathon pitch** → [thesis.md](./thesis.md)
