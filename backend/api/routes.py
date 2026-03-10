"""
REST API routes for InfiniteCanvas orchestration backend.
Provides endpoints for scene resolution, preload hints, and manual intent injection.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

from orchestration.scene_conductor import SceneConductor, GENRES, BEATS
from orchestration.state_machine import NarrativeStateMachine
from orchestration.audio_crossfader import AudioCrossfader

router = APIRouter()


class IntentRequest(BaseModel):
    genre: Optional[str] = Field(None, description="Target genre")
    action: str = Field("change_genre", description="change_genre|next_beat|reset")
    confidence: float = Field(0.9, ge=0.0, le=1.0)
    emotional_intensity: float = Field(0.5, ge=0.0, le=1.0)
    beat_index: int = Field(0, ge=0, le=2)


class PreloadRequest(BaseModel):
    current_genre: str
    beat_index: int


@router.post("/intent")
async def resolve_intent(body: IntentRequest, request: Request):
    """
    REST fallback for intent resolution (used when WebSocket not available
    or for testing purposes).
    """
    scene_graph = getattr(request.app.state, "scene_graph", {})
    conductor = SceneConductor(scene_graph)
    state_machine = NarrativeStateMachine()

    intent = body.model_dump()
    validated = state_machine.validate_intent(intent)
    if not validated:
        return {
            "status": "rejected",
            "feedback": state_machine.get_conflict_message(intent),
        }

    scene = conductor.resolve(validated)
    return {"status": "ok", "scene": scene}


@router.get("/scenes")
async def list_scenes(request: Request):
    """List all available pre-generated scene segments."""
    scenes = []
    for genre in GENRES:
        for i, beat in enumerate(BEATS):
            scenes.append({
                "genre": genre,
                "beat": beat,
                "beat_index": i,
                "video_url": f"/assets/video/{genre}_{beat}.mp4",
            })
    return {"scenes": scenes, "total": len(scenes)}


@router.post("/preload-hints")
async def preload_hints(body: PreloadRequest, request: Request):
    """Return asset URLs to preload for likely next transitions."""
    scene_graph = getattr(request.app.state, "scene_graph", {})
    conductor = SceneConductor(scene_graph)
    hints = conductor.get_preload_hints(body.current_genre, body.beat_index)
    return {"hints": hints}


@router.get("/audio-transition")
async def audio_transition(from_genre: str, to_genre: str, duration_ms: int = 800):
    """Get audio stem transition plan for a genre switch."""
    if from_genre not in GENRES or to_genre not in GENRES:
        raise HTTPException(400, f"Invalid genre. Valid: {GENRES}")
    crossfader = AudioCrossfader()
    plan = crossfader.build_transition_plan(from_genre, to_genre, duration_ms)
    return plan
