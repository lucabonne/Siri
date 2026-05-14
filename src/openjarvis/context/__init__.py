"""Passive local context awareness for OpenJarvis."""

from openjarvis.context.layer import ContextLayer
from openjarvis.context.models import (
    DesktopContext,
    ProjectContext,
    RepoIndex,
    RepoSummary,
)

__all__ = [
    "ContextLayer",
    "DesktopContext",
    "ProjectContext",
    "RepoIndex",
    "RepoSummary",
]
