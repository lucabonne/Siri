import uuid
from datetime import datetime
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field


class FeedbackEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_module: str = Field(
        ...,
        description="Module that generated the feedback (e.g., 'research', 'coding')",
    )
    target_id: str = Field(..., description="ID of the item being rated")
    rating: Literal["thumbs_up", "thumbs_down"]
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context about the rated item"
    )


class PreferenceWeight(BaseModel):
    key: str
    weight: float = Field(
        default=1.0, description="Multiplier for preference importance"
    )


class ToolUsefulness(BaseModel):
    tool_name: str
    success_count: int = 0
    failure_count: int = 0
    thumbs_up: int = 0
    thumbs_down: int = 0

    @property
    def score(self) -> float:
        total = self.thumbs_up + self.thumbs_down
        if total == 0:
            return 1.0
        return (self.thumbs_up + 1) / (total + 2)  # Laplace smoothing


class LearningState(BaseModel):
    feedback_history: list[FeedbackEvent] = Field(default_factory=list)
    preferences: dict[str, float] = Field(default_factory=dict)
    tool_scores: dict[str, ToolUsefulness] = Field(default_factory=dict)
    memory_adjustments: dict[str, float] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class ExportedLearningState(BaseModel):
    version: str = "1.0"
    exported_at: datetime = Field(default_factory=datetime.utcnow)
    state: LearningState
