from datetime import datetime
from typing import List

from .models import FeedbackEvent, LearningState


class FeedbackManager:
    """Manages the history and recording of explicit user feedback."""

    def __init__(self, state: LearningState):
        self.state = state

    def record_feedback(
        self, source_module: str, target_id: str, rating: str, context: dict = None
    ) -> FeedbackEvent:
        """Records explicit thumbs up/down feedback."""
        if rating not in ["thumbs_up", "thumbs_down"]:
            raise ValueError("Rating must be 'thumbs_up' or 'thumbs_down'")

        event = FeedbackEvent(
            source_module=source_module,
            target_id=target_id,
            rating=rating,
            context=context or {},
        )
        self.state.feedback_history.append(event)
        self.state.last_updated = datetime.utcnow()
        return event

    def get_history(self, limit: int = 50) -> List[FeedbackEvent]:
        """Returns the most recent feedback events."""
        return sorted(
            self.state.feedback_history, key=lambda x: x.timestamp, reverse=True
        )[:limit]

    def get_feedback_for_target(self, target_id: str) -> List[FeedbackEvent]:
        """Returns all feedback events for a specific target ID."""
        return [e for e in self.state.feedback_history if e.target_id == target_id]

    def clear_history(self) -> None:
        """Clears all feedback history."""
        self.state.feedback_history.clear()
        self.state.last_updated = datetime.utcnow()
