import json
import os
from pathlib import Path
from typing import Any, Dict

from .feedback import FeedbackManager
from .memory import MemoryLearningManager
from .models import ExportedLearningState, LearningState
from .preferences import PreferenceManager
from .ranking import RankingManager


class LearningService:
    """
    Coordinates explicit user feedback, preference adjustment, ranking,
    and memory importance modifications. All learning is explicit and local.
    """

    def __init__(self, state_dir: str = "~/.openjarvis/state/learning"):
        self.state_dir = Path(os.path.expanduser(state_dir))
        self.state_file = self.state_dir / "learning_state.json"
        self.state = self._load_state()

        self.feedback = FeedbackManager(self.state)
        self.preferences = PreferenceManager(self.state)
        self.ranking = RankingManager(self.state)
        self.memory = MemoryLearningManager(self.state)

    def _load_state(self) -> LearningState:
        """Loads learning state from local disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    data = json.load(f)
                    return LearningState.model_validate(data)
            except Exception as e:
                print(f"Failed to load learning state, starting fresh: {e}")
        return LearningState()

    def _save_state(self) -> None:
        """Saves current learning state to local disk."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            f.write(self.state.model_dump_json(indent=2))

    def record_feedback(
        self, source_module: str, target_id: str, rating: str, context: dict = None
    ) -> None:
        """Record explicit feedback and apply deterministic weight updates."""
        event = self.feedback.record_feedback(source_module, target_id, rating, context)

        # Determine how to update preferences/rankings based on source module
        if source_module == "tool_execution":
            self.ranking.record_tool_feedback(target_id, rating)
        elif source_module == "memory_search":
            self.memory.adjust_memory_importance(target_id, event)
        elif source_module in ["research", "coding", "workflow", "autonomy"]:
            # Preference adjustment based on topic or category if available in context
            if context and "topic" in context:
                self.preferences.apply_feedback_to_preference(
                    f"topic_{context['topic']}", event
                )

        self._save_state()

    def get_learning_summary(self) -> Dict[str, Any]:
        """Provides a summary of the current learning state for Mission Control."""
        return {
            "feedback_count": len(self.state.feedback_history),
            "preferences": self.preferences.get_all_preferences(),
            "tool_scores": {k: v.score for k, v in self.state.tool_scores.items()},
            "memory_adjustments_count": len(self.state.memory_adjustments),
            "last_updated": self.state.last_updated.isoformat(),
        }

    def reset_learning_state(self) -> None:
        """Completely clears all explicit learning data."""
        self.feedback.clear_history()
        self.preferences.reset_preferences()
        self.ranking.reset_tool_scores()
        self.memory.reset_memory_adjustments()
        self._save_state()

    def export_state(self) -> str:
        """Exports the learning state for backup/transfer."""
        export_model = ExportedLearningState(state=self.state)
        return export_model.model_dump_json(indent=2)

    def import_state(self, json_data: str) -> bool:
        """Imports a learning state from JSON, replacing the current state."""
        try:
            data = json.loads(json_data)
            export_model = ExportedLearningState.model_validate(data)
            self.state = export_model.state

            # Re-initialize managers with new state reference
            self.feedback = FeedbackManager(self.state)
            self.preferences = PreferenceManager(self.state)
            self.ranking = RankingManager(self.state)
            self.memory = MemoryLearningManager(self.state)

            self._save_state()
            return True
        except Exception as e:
            print(f"Failed to import learning state: {e}")
            return False
