from typing import TYPE_CHECKING, Any, Callable, List

if TYPE_CHECKING:
    from .preferences import PreferenceManager

from .models import LearningState, ToolUsefulness


class RankingManager:
    """Ranking utilities for workspace suggestions based on explicit feedback scores."""

    def __init__(self, state: LearningState):
        self.state = state

    def record_tool_feedback(self, tool_name: str, rating: str):
        """Update tool usefulness score based on explicit thumbs up/down."""
        if tool_name not in self.state.tool_scores:
            self.state.tool_scores[tool_name] = ToolUsefulness(tool_name=tool_name)

        score = self.state.tool_scores[tool_name]

        if rating == "thumbs_up":
            score.thumbs_up += 1
        elif rating == "thumbs_down":
            score.thumbs_down += 1

    def record_tool_execution(self, tool_name: str, success: bool):
        """Update basic execution success rates."""
        if tool_name not in self.state.tool_scores:
            self.state.tool_scores[tool_name] = ToolUsefulness(tool_name=tool_name)

        score = self.state.tool_scores[tool_name]
        if success:
            score.success_count += 1
        else:
            score.failure_count += 1

    def rank_tools(self, available_tools: List[str]) -> List[str]:
        """Returns tools sorted by explicit usefulness score."""

        def get_score(tool: str) -> float:
            if tool in self.state.tool_scores:
                return self.state.tool_scores[tool].score
            return 1.0  # default score

        return sorted(available_tools, key=get_score, reverse=True)

    def rank_items(
        self,
        items: List[Any],
        key_fn: Callable[[Any], str],
        preference_manager: "PreferenceManager",
    ) -> List[Any]:
        """Rank arbitrary items based on learned preference weights."""

        def get_item_score(item: Any) -> float:
            key = key_fn(item)
            return preference_manager.get_preference(key)

        return sorted(items, key=get_item_score, reverse=True)

    def reset_tool_scores(self) -> None:
        """Resets all tool scores."""
        self.state.tool_scores.clear()
