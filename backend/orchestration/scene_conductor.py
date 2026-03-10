"""
SceneConductor — semantic matcher that resolves a viewer intent
to the best available pre-generated video segment.
"""

import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GENRES = ["noir", "romcom", "horror", "scifi"]
BEATS = ["opening", "confrontation", "climax"]

# Genre adjacency graph — cosine-like semantic distance
GENRE_DISTANCES = {
    ("noir", "romcom"): 0.7,
    ("noir", "horror"): 0.3,
    ("noir", "scifi"): 0.5,
    ("romcom", "horror"): 0.9,
    ("romcom", "scifi"): 0.6,
    ("horror", "scifi"): 0.4,
}


def genre_distance(a: str, b: str) -> float:
    if a == b:
        return 0.0
    key = tuple(sorted([a, b]))
    return GENRE_DISTANCES.get(key, 0.8)


class SceneConductor:
    """
    Orchestrates which video segment to serve given the current state
    and an incoming viewer intent.
    """

    def __init__(self, scene_graph: dict):
        self.scene_graph = scene_graph

    def resolve(self, intent: dict) -> dict:
        """
        Given a parsed intent, return the scene descriptor:
        {genre, beat, url, transition_type, audio_stems}
        """
        target_genre = intent.get("genre") or "noir"
        if target_genre not in GENRES:
            target_genre = self._closest_genre(target_genre)

        beat_index = intent.get("beat_index", 0)
        beat_name = BEATS[min(beat_index, len(BEATS) - 1)]

        scene_key = f"{target_genre}_{beat_name}"
        scene_meta = self.scene_graph.get(scene_key, {})

        return {
            "genre": target_genre,
            "beat": beat_name,
            "beat_index": BEATS.index(beat_name),
            "video_url": scene_meta.get("video_url", f"/assets/video/{scene_key}.mp4"),
            "audio_stems": scene_meta.get("audio_stems", []),
            "emotional_valence": scene_meta.get("emotional_valence", 0.0),
            "transition_duration_ms": self._calc_transition_duration(
                intent.get("emotional_intensity", 0.5)
            ),
        }

    def _closest_genre(self, raw_genre: str) -> str:
        """Fuzzy match raw genre string to closest known genre."""
        raw = raw_genre.lower()
        mappings = {
            "sci-fi": "scifi",
            "science fiction": "scifi",
            "cyber": "scifi",
            "cyberpunk": "scifi",
            "romantic": "romcom",
            "romance": "romcom",
            "comedy": "romcom",
            "dark": "noir",
            "mystery": "noir",
            "thriller": "noir",
            "scary": "horror",
            "scary movie": "horror",
            "suspense": "horror",
        }
        for key, genre in mappings.items():
            if key in raw:
                return genre
        return "noir"

    def _calc_transition_duration(self, intensity: float) -> int:
        """Higher emotional intensity → faster transition (more jarring)."""
        base_ms = 800
        min_ms = 300
        return max(min_ms, int(base_ms * (1.0 - intensity * 0.6)))

    def get_preload_hints(self, current_genre: str, beat_index: int) -> list[str]:
        """Return URLs to preload based on likely next transitions."""
        hints = []
        next_beat = min(beat_index + 1, len(BEATS) - 1)
        # Preload same genre next beat
        hints.append(f"/assets/video/{current_genre}_{BEATS[next_beat]}.mp4")
        # Preload closest genre same beat
        closest = min(
            [g for g in GENRES if g != current_genre],
            key=lambda g: genre_distance(current_genre, g),
        )
        hints.append(f"/assets/video/{closest}_{BEATS[beat_index]}.mp4")
        return hints
