"""
InfiniteCanvas: The Liquid Movie — FastAPI Orchestration Backend
Handles Gemini Live API proxying, scene orchestration, and asset serving.
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from orchestration.scene_conductor import SceneConductor
from orchestration.state_machine import NarrativeStateMachine
from gemini.live_client import GeminiLiveClient
from api.routes import router as api_router

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent.parent / "assets"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("InfiniteCanvas backend starting up...")
    # Pre-load scene graph metadata
    app.state.scene_graph = _load_scene_graph()
    app.state.active_sessions: dict[str, dict] = {}
    yield
    logger.info("InfiniteCanvas backend shutting down.")


app = FastAPI(
    title="InfiniteCanvas Orchestration API",
    description="Reality conductor for the Liquid Movie",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# Serve pre-generated video assets
if (ASSETS_DIR / "video").exists():
    app.mount("/assets/video", StaticFiles(directory=str(ASSETS_DIR / "video")), name="video")


def _load_scene_graph() -> dict:
    graph_path = ASSETS_DIR / "metadata" / "scene_graph.json"
    if graph_path.exists():
        with open(graph_path) as f:
            return json.load(f)
    return {}


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """
    WebSocket endpoint that:
    1. Receives raw PCM audio from the browser
    2. Forwards to Gemini Live API for real-time intent parsing
    3. Sends structured intent events back to the client
    """
    await websocket.accept()
    session_id = id(websocket)
    logger.info(f"Voice session started: {session_id}")

    conductor = SceneConductor(app.state.scene_graph)
    state_machine = NarrativeStateMachine()
    gemini_client = GeminiLiveClient(
        api_key=os.environ.get("GEMINI_API_KEY", ""),
        on_intent=lambda intent: asyncio.create_task(
            _handle_intent(websocket, conductor, state_machine, intent)
        ),
    )

    try:
        await websocket.send_json({"type": "connected", "session_id": str(session_id)})
        await gemini_client.start()

        async for message in websocket.iter_bytes():
            # Forward raw PCM audio bytes to Gemini Live
            await gemini_client.send_audio(message)

    except WebSocketDisconnect:
        logger.info(f"Voice session ended: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error in session {session_id}: {e}")
    finally:
        await gemini_client.stop()


async def _handle_intent(
    websocket: WebSocket,
    conductor: SceneConductor,
    state_machine: NarrativeStateMachine,
    raw_intent: dict,
):
    """Validate intent against narrative state, resolve scene, push to client."""
    try:
        validated = state_machine.validate_intent(raw_intent)
        if not validated:
            feedback = state_machine.get_conflict_message(raw_intent)
            await websocket.send_json({"type": "intent", "intent": {"feedback": feedback}})
            return

        scene = conductor.resolve(validated)
        await websocket.send_json({
            "type": "intent",
            "intent": {
                **validated,
                "scene": scene,
            },
        })
        state_machine.apply(validated)
    except Exception as e:
        logger.error(f"Intent handling error: {e}")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "infinite-canvas-orchestrator"}


@app.get("/api/scene-graph")
async def get_scene_graph():
    return app.state.scene_graph
