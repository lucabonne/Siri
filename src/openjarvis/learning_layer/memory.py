from .models import FeedbackEvent, LearningState


class MemoryLearningManager:
    """Adjusts memory importance scores deterministically based on explicit feedback."""

    def __init__(self, state: LearningState):
        self.state = state

    def adjust_memory_importance(
        self, memory_id: str, feedback: FeedbackEvent, step: float = 0.2
    ) -> float:
        """
        Adjusts the importance multiplier for a memory based on explicit feedback.
        """
        current_multiplier = self.state.memory_adjustments.get(memory_id, 1.0)

        if feedback.rating == "thumbs_up":
            new_multiplier = current_multiplier + step
        else:
            new_multiplier = max(0.1, current_multiplier - step)

        self.state.memory_adjustments[memory_id] = new_multiplier
        return new_multiplier

    def get_memory_multiplier(self, memory_id: str) -> float:
        """Gets the learned multiplier for a specific memory."""
        return self.state.memory_adjustments.get(memory_id, 1.0)

    def apply_learning_to_memories(self, memory_results: list[dict]) -> list[dict]:
        """
        Takes a list of search results from the Memory subsystem and adjusts their
        scores based on explicit learning multipliers.
        """
        for result in memory_results:
            memory_id = result.get("id")
            if memory_id:
                multiplier = self.get_memory_multiplier(memory_id)
                # Ensure we only boost/penalize score if it exists
                if "score" in result:
                    result["score"] = result["score"] * multiplier

        # Re-sort after adjusting scores
        if all("score" in r for r in memory_results):
            memory_results.sort(key=lambda x: x["score"], reverse=True)

        return memory_results

    def reset_memory_adjustments(self) -> None:
        """Resets all memory adjustments to 1.0."""
        self.state.memory_adjustments.clear()
