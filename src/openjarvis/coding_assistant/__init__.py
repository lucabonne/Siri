"""Passive local coding assistant subsystem."""

from openjarvis.coding_assistant.models import (
    ArchitectureExplanation,
    BuildAnalysis,
    BuildFailure,
    CodingPanelSnapshot,
    CodingStackProfile,
    DebuggingSummary,
    ProjectHealthSummary,
    SafeFixSuggestion,
)
from openjarvis.coding_assistant.service import (
    CodingAssistantService,
    get_coding_assistant_service,
)

__all__ = [
    "ArchitectureExplanation",
    "BuildAnalysis",
    "BuildFailure",
    "CodingAssistantService",
    "CodingPanelSnapshot",
    "CodingStackProfile",
    "DebuggingSummary",
    "ProjectHealthSummary",
    "SafeFixSuggestion",
    "get_coding_assistant_service",
]
