"""Typed models for Siri Autonomous Research Mode Phase 1."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ResearchPlan:
    """Deterministic research plan for one user question."""

    question: str
    search_strategy: list[str]
    subtopics: list[str]
    open_questions: list[str]
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ResearchSource:
    """A source collected during a local-first research run."""

    id: str
    title: str
    url: str
    access_date: str
    relevance: float = 0.0
    extracted_claims: list[str] = field(default_factory=list)
    snippet: str = ""
    source_type: str = "cached"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Citation:
    """Numbered citation for report generation."""

    id: str
    source_id: str
    label: str
    title: str
    url: str
    access_date: str
    relevance: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ResearchReport:
    """Generated research report payload."""

    id: str
    question: str
    title: str
    notes: list[str]
    summary: str
    citations: list[Citation]
    unresolved_questions: list[str]
    body: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["citations"] = [citation.to_dict() for citation in self.citations]
        return data


@dataclass(slots=True)
class ResearchSession:
    """Stored one-shot research workflow state."""

    id: str
    question: str
    status: str
    plan: ResearchPlan
    sources: list[ResearchSource]
    report: ResearchReport | None
    memory_ids: list[str]
    privacy_mode: bool
    cached_sources_only: bool
    local_only: bool
    passive_only: bool
    active_mode_id: str = ""
    workspace_agent_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "status": self.status,
            "plan": self.plan.to_dict(),
            "sources": [source.to_dict() for source in self.sources],
            "report": self.report.to_dict() if self.report else None,
            "memory_ids": list(self.memory_ids),
            "privacy_mode": self.privacy_mode,
            "cached_sources_only": self.cached_sources_only,
            "local_only": self.local_only,
            "passive_only": self.passive_only,
            "active_mode_id": self.active_mode_id,
            "workspace_agent_id": self.workspace_agent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }


__all__ = [
    "Citation",
    "ResearchPlan",
    "ResearchReport",
    "ResearchSession",
    "ResearchSource",
]
