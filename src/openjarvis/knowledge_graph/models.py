"""Typed contracts for the local Knowledge Graph."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class GraphNodeType(str, Enum):
    note = "note"
    memory = "memory"
    research = "research"
    source = "source"
    project = "project"
    decision = "decision"
    timeline_event = "timeline_event"
    repo = "repo"
    code = "code"
    learning = "learning"
    concept = "concept"


class GraphRelationship(str, Enum):
    references = "references"
    related_to = "related_to"
    supports = "supports"
    contradicts = "contradicts"
    derived_from = "derived_from"
    belongs_to = "belongs_to"
    decided = "decided"
    led_to = "led_to"
    mentions = "mentions"
    implements = "implements"
    depends_on = "depends_on"
    sourced_from = "sourced_from"


class GraphNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_type: GraphNodeType | str
    title: str
    text: str = ""
    ref_id: Optional[str] = None
    ref_table: Optional[str] = None
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    pinned_root: bool = False
    created_at: str = ""
    updated_at: str = ""


class GraphEdge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    relationship: GraphRelationship | str
    weight: float = 1.0
    directed: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class TimelineEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_id: Optional[str] = None
    project_id: Optional[str] = None
    event_type: str = "event"
    title: str
    summary: str = ""
    occurred_at: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class ProjectDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_id: Optional[str] = None
    project_id: str
    title: str
    decision: str
    rationale: str = ""
    status: str = "accepted"
    made_at: str = ""
    note_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class GraphPath(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    depth: int = 0


class GraphNeighborhood(BaseModel):
    center: GraphNode | None = None
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    roots: list[GraphNode] = Field(default_factory=list)
    local_only: bool = True


class NeighborhoodSearchResult(BaseModel):
    node: GraphNode
    score: float
    reasons: list[str] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class CreateGraphNodeRequest(BaseModel):
    node_type: GraphNodeType | str
    title: str
    text: str = ""
    ref_id: Optional[str] = None
    ref_table: Optional[str] = None
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    pinned_root: bool = False


class CreateGraphEdgeRequest(BaseModel):
    source_id: str
    target_id: str
    relationship: GraphRelationship | str
    weight: float = 1.0
    directed: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "GraphNodeType",
    "GraphRelationship",
    "GraphNode",
    "GraphEdge",
    "TimelineEvent",
    "ProjectDecision",
    "GraphPath",
    "GraphNeighborhood",
    "NeighborhoodSearchResult",
    "CreateGraphNodeRequest",
    "CreateGraphEdgeRequest",
]
