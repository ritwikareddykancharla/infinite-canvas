"""
AudioCrossfader — manages stem-based audio transitions between genres.
Uses scipy for envelope calculations; actual stem files are pre-generated.
"""

import asyncio
import logging
import numpy as np
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

STEM_TYPES = ["bass", "drums", "melody", "ambient"]
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets" / "audio"

# Genre-specific stem weights (which stems are prominent per genre)
GENRE_STEM_WEIGHTS = {
    "noir":   {"bass": 0.9, "drums": 0.4, "melody": 0.7, "ambient": 0.8},
    "romcom": {"bass": 0.5, "drums": 0.6, "melody": 1.0, "ambient": 0.4},
    "horror": {"bass": 0.3, "drums": 0.2, "melody": 0.1, "ambient": 1.0},
    "scifi":  {"bass": 0.7, "drums": 0.8, "melody": 0.5, "ambient": 0.9},
}


def compute_crossfade_envelope(
    duration_samples: int,
    curve: str = "equal_power",
) -> tuple[np.ndarray, np.ndarray]:
    """
    Returns (fade_out, fade_in) gain envelopes using equal-power or linear curves.
    """
    t = np.linspace(0, np.pi / 2, duration_samples)
    if curve == "equal_power":
        fade_out = np.cos(t)
        fade_in = np.sin(t)
    else:
        fade_out = np.linspace(1, 0, duration_samples)
        fade_in = np.linspace(0, 1, duration_samples)
    return fade_out, fade_in


class AudioCrossfader:
    """
    Orchestrates stem-level crossfade between genre audio tracks.
    Yields crossfade metadata that the frontend applies via Web Audio API.
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate

    def build_transition_plan(
        self,
        from_genre: str,
        to_genre: str,
        duration_ms: int = 800,
    ) -> dict:
        """
        Returns a transition plan that the frontend Web Audio API executes:
        {stems: [{type, from_gain, to_gain, duration_ms}]}
        """
        from_weights = GENRE_STEM_WEIGHTS.get(from_genre, {})
        to_weights = GENRE_STEM_WEIGHTS.get(to_genre, {})

        stems = []
        for stem in STEM_TYPES:
            stems.append({
                "type": stem,
                "from_gain": from_weights.get(stem, 0.5),
                "to_gain": to_weights.get(stem, 0.5),
                "duration_ms": duration_ms,
                "from_url": f"/assets/audio/{from_genre}_{stem}.mp3",
                "to_url": f"/assets/audio/{to_genre}_{stem}.mp3",
                "curve": "equal_power",
            })

        return {
            "from_genre": from_genre,
            "to_genre": to_genre,
            "total_duration_ms": duration_ms,
            "stems": stems,
        }

    def stem_url(self, genre: str, stem_type: str) -> str:
        return f"/assets/audio/{genre}_{stem_type}.mp3"
