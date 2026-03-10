"""
InfiniteCanvas ADK Agent — orchestrates scene transitions and generates
director's commentary using Google Agent Development Kit (ADK).

Usage:
    from adk.agent import run_agent
    result = await run_agent("Generate director's commentary for history: [...]")
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GENRES = ["noir", "romcom", "horror", "scifi"]
BEATS = ["opening", "confrontation", "climax"]

PERSONALITY_READS = {
    "noir": "You gravitate toward shadows. A storyteller of moral ambiguity who finds truth in the darkness.",
    "romcom": "You believe in connection. An optimist who sees beauty in vulnerability and human warmth.",
    "horror": "You embrace tension. A fearless explorer drawn to the edges of comfort and safety.",
    "scifi": "You chase wonder. A visionary who looks beyond the present into infinite possibility.",
}


# ── ADK tool functions ────────────────────────────────────────────────────────

def change_scene(genre: str, beat_index: int = 0) -> dict:
    """Change the movie scene to the specified genre and beat.

    Args:
        genre: Target genre — one of noir, romcom, horror, scifi.
        beat_index: Story beat index. 0 = opening, 1 = confrontation, 2 = climax.

    Returns:
        Scene descriptor with video URL and transition metadata.
    """
    if genre not in GENRES:
        return {"error": f"Invalid genre '{genre}'. Choose from: {GENRES}"}
    beat_name = BEATS[min(beat_index, len(BEATS) - 1)]
    return {
        "genre": genre,
        "beat": beat_name,
        "beat_index": BEATS.index(beat_name),
        "video_url": f"/assets/video/{genre}_{beat_name}.mp4",
        "status": "scene_changed",
    }


def get_available_genres() -> dict:
    """Return all available genres and story beats with their cinematic descriptions.

    Returns:
        Dictionary describing genres and beats.
    """
    return {
        "genres": {
            "noir": "Shadows, moral ambiguity, jazz undertones",
            "romcom": "Golden light, warmth, piano melodies",
            "horror": "Cold dread, ambient drone, darkness",
            "scifi": "Neon cyan, synth music, wonder and awe",
        },
        "beats": {
            "opening": "Establishing the scene and characters",
            "confrontation": "Rising tension and conflict",
            "climax": "Peak emotional moment",
        },
    }


def generate_director_commentary(narrative_history: list) -> dict:
    """Analyze the viewer's narrative choices and produce a personality read.

    Args:
        narrative_history: Ordered list of dicts with 'genre' and 'beat' keys
                           representing each scene the viewer chose.

    Returns:
        Commentary dict with dominant_genre, personality_read, genre_distribution,
        and the full narrative_arc.
    """
    if not narrative_history:
        return {"commentary": "No narrative history to analyze yet."}

    genre_counts: dict[str, int] = {}
    for entry in narrative_history:
        g = entry.get("genre", "noir")
        genre_counts[g] = genre_counts.get(g, 0) + 1

    dominant = max(genre_counts, key=genre_counts.get)
    total = len(narrative_history)
    distribution = {g: round(c / total * 100) for g, c in genre_counts.items()}

    return {
        "dominant_genre": dominant,
        "personality_read": PERSONALITY_READS.get(dominant, "A unique directorial voice."),
        "genre_distribution": distribution,
        "total_choices": total,
        "narrative_arc": [e.get("genre") for e in narrative_history],
    }


# ── ADK agent factory ─────────────────────────────────────────────────────────

AGENT_INSTRUCTION = """You are the InfiniteCanvas Reality Conductor — an AI film director.

Your role:
1. Help viewers direct their "liquid movie" by understanding cinematic intent.
2. Resolve which scene segment to play next via change_scene.
3. Analyze narrative choices with generate_director_commentary.

Genres: noir (shadows/jazz), romcom (warmth/piano), horror (dread/drone), scifi (wonder/synth).
Beats: opening (0), confrontation (1), climax (2).

Always respond with the tool result, then add a single-sentence cinematic observation.
"""


def create_agent():
    """Instantiate the InfiniteCanvas ADK LlmAgent with scene tools.

    Returns the agent, or None if google-adk is not installed.
    """
    try:
        from google.adk.agents import LlmAgent
        from google.adk.tools import FunctionTool

        agent = LlmAgent(
            name="infinite_canvas_conductor",
            model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            description="InfiniteCanvas Reality Conductor — cinematic scene orchestration",
            instruction=AGENT_INSTRUCTION,
            tools=[
                FunctionTool(change_scene),
                FunctionTool(get_available_genres),
                FunctionTool(generate_director_commentary),
            ],
        )
        logger.info("ADK agent 'infinite_canvas_conductor' created")
        return agent
    except ImportError:
        logger.warning("google-adk not installed — ADK agent unavailable")
        return None


async def run_agent(user_message: str, session_id: str = "default") -> str:
    """Run the ADK agent with a user message and return the text response.

    Args:
        user_message: The viewer's instruction or query.
        session_id: Unique identifier for this viewing session.

    Returns:
        Agent's text response, or an error string if ADK is unavailable.
    """
    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types as genai_types

        agent = create_agent()
        if agent is None:
            return "ADK agent unavailable — check google-adk installation."

        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="infinite_canvas",
            session_service=session_service,
        )

        user_content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=user_message)],
        )

        response_text = ""
        async for event in runner.run_async(
            user_id="viewer",
            session_id=session_id,
            new_message=user_content,
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        response_text += part.text

        return response_text or "No response from agent."

    except Exception as e:
        logger.error(f"ADK agent run error: {e}")
        return f"Agent error: {e}"
