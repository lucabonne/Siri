from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


class MemoryWeights(BaseModel):
    """Explicit importance weights for different memory types."""

    user_facts: float = Field(default=1.0, description="Weight for user-related facts")
    project_context: float = Field(
        default=1.0, description="Weight for project context"
    )
    coding_patterns: float = Field(
        default=1.0, description="Weight for coding patterns"
    )
    engineering_rules: float = Field(
        default=1.0, description="Weight for engineering rules"
    )
    default_weight: float = Field(
        default=1.0, description="Default weight for unclassified memories"
    )


class MissionControlDefaults(BaseModel):
    """Default states for Mission Control UI."""

    default_tab: str = Field(
        default="home", description="Default tab to open in Mission Control"
    )
    theme: str = Field(
        default="system", description="Theme preference: system, light, dark"
    )


class Preferences(BaseModel):
    """User preferences for Siri behavior."""

    preferred_workspace: str = Field(
        default="coding",
        description="Preferred agent workspace (e.g., coding, engineering, research)",
    )
    coding_vs_engineering: str = Field(
        default="coding", description="Preference between coding and engineering tasks"
    )
    voice_interaction: bool = Field(
        default=False, description="Whether voice interactions are enabled by default"
    )
    wake_word_preference: bool = Field(
        default=False, description="Whether wake word is enabled by default"
    )
    quiet_mode_preference: bool = Field(
        default=False, description="Whether quiet mode is enabled by default"
    )
    mission_control_defaults: MissionControlDefaults = Field(
        default_factory=MissionControlDefaults
    )


class Routines(BaseModel):
    """Explicit routines configuration."""

    morning_briefing_enabled: bool = Field(
        default=False, description="Enable morning briefing routines"
    )
    morning_briefing_time: Optional[str] = Field(
        default=None, description="Preferred time for morning briefing (HH:MM)"
    )
    auto_start_workflows: List[str] = Field(
        default_factory=list, description="List of workflow IDs to run on profile load"
    )


class Profile(BaseModel):
    """A personalized user profile."""

    id: str = Field(..., description="Unique profile ID")
    name: str = Field(..., description="Display name for the profile")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    preferences: Preferences = Field(default_factory=Preferences)
    routines: Routines = Field(default_factory=Routines)
    memory_weights: MemoryWeights = Field(default_factory=MemoryWeights)
