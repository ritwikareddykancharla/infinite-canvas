"""
NarrativeStateMachine — enforces narrative coherence across viewer commands.
Prevents contradictory states (e.g. "she's the villain" then "they fall in love").
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# Intent compatibility matrix — pairs of (committed_state, new_intent_genre) that conflict
INCOMPATIBLE = {
    "villain_committed": {"romcom"},
    "lovers_committed": {"horror"},
    "hero_dead_committed": {"romcom", "scifi"},
}

# Genre-specific narrative "locks" applied when genre is selected
GENRE_LOCKS = {
    "horror": "villain_committed",
    "noir": None,
    "romcom": "lovers_committed",
    "scifi": None,
}


@dataclass
class NarrativeState:
    current_genre: str = "noir"
    current_beat: int = 0
    committed_states: set = field(default_factory=set)
    history: list = field(default_factory=list)


class NarrativeStateMachine:
    def __init__(self):
        self.state = NarrativeState()

    def validate_intent(self, intent: dict) -> Optional[dict]:
        """
        Returns the (possibly modified) intent if valid, None if rejected.
        """
        action = intent.get("action")
        target_genre = intent.get("genre")

        if action == "reset":
            return intent

        if action == "next_beat":
            return intent

        if target_genre and action == "change_genre":
            # Check for committed state conflicts
            for committed, blocked_genres in INCOMPATIBLE.items():
                if committed in self.state.committed_states:
                    if target_genre in blocked_genres:
                        logger.info(
                            f"Intent rejected: {target_genre} conflicts with {committed}"
                        )
                        return None

        return intent

    def get_conflict_message(self, intent: dict) -> str:
        """Generate a natural language conflict explanation."""
        target_genre = intent.get("genre", "")
        messages = {
            "romcom": "That would conflict with the established darkness. Try horror or noir instead?",
            "horror": "That would undo the connection they just made. Try noir or sci-fi instead?",
        }
        return messages.get(
            target_genre,
            f"That choice conflicts with the current narrative. Try resetting to explore a new path.",
        )

    def apply(self, intent: dict):
        """Commit a validated intent to narrative state."""
        action = intent.get("action")
        genre = intent.get("genre")

        if action == "reset":
            self.state = NarrativeState()
            return

        if action == "next_beat":
            self.state.current_beat = min(self.state.current_beat + 1, 2)

        if action == "change_genre" and genre:
            self.state.history.append({
                "genre": self.state.current_genre,
                "beat": self.state.current_beat,
            })
            self.state.current_genre = genre
            lock = GENRE_LOCKS.get(genre)
            if lock:
                self.state.committed_states.add(lock)

    @property
    def current_state(self) -> dict:
        return {
            "genre": self.state.current_genre,
            "beat": self.state.current_beat,
            "committed_states": list(self.state.committed_states),
        }
