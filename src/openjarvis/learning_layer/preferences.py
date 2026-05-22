from typing import Dict

from .models import FeedbackEvent, LearningState


class PreferenceManager:
    """Translates explicit feedback into preference weights without autonomous drift."""

    def __init__(self, state: LearningState):
        self.state = state

    def apply_feedback_to_preference(
        self, key: str, feedback: FeedbackEvent, step: float = 0.1
    ) -> float:
        """
        Adjusts a preference weight based on explicit feedback.
        Thumbs up increases the weight, thumbs down decreases it.
        """
        current_weight = self.state.preferences.get(key, 1.0)

        if feedback.rating == "thumbs_up":
            new_weight = current_weight + step
        else:
            new_weight = max(0.1, current_weight - step)  # Keep above 0

        self.state.preferences[key] = new_weight
        return new_weight

    def get_preference(self, key: str, default: float = 1.0) -> float:
        """Gets the current weight for a preference."""
        return self.state.preferences.get(key, default)

    def get_all_preferences(self) -> Dict[str, float]:
        """Returns all preference weights."""
        return self.state.preferences.copy()

    def reset_preferences(self) -> None:
        """Resets all preferences to default (1.0)."""
        self.state.preferences.clear()
