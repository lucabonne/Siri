"""Coordinating service for the local Knowledge Graph."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

from openjarvis.knowledge_graph import (
    edges,
    graph_search,
    nodes,
    relationships,
    timelines,
)
from openjarvis.knowledge_graph import project_links as decisions
from openjarvis.knowledge_graph.models import GraphNodeType, GraphRelationship

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".openjarvis" / "knowledge_graph.db"


class KnowledgeGraphService:
    """Local-only graph layer that augments vault and memory records."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        vault_service: Any | None = None,
        memory_service: Any | None = None,
        repo_index_service: Any | None = None,
        coding_assistant_service: Any | None = None,
        learning_service: Any | None = None,
        research_service: Any | None = None,
    ) -> None:
        if db_path is None:
            db_path = _DEFAULT_DB
        self.db_path = Path(db_path).expanduser()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._fts_enabled = nodes.ensure_schema(self._conn)
        edges.ensure_schema(self._conn)
        timelines.ensure_schema(self._conn)
        decisions.ensure_schema(self._conn)
        self.vault_service = vault_service
        self.memory_service = memory_service
        self.repo_index_service = repo_index_service
        self.coding_assistant_service = coding_assistant_service
        self.learning_service = learning_service
        self.research_service = research_service

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------

    def create_node(
        self,
        *,
        node_type: str,
        title: str,
        text: str = "",
        ref_id: str | None = None,
        ref_table: str | None = None,
        source: str = "",
        metadata: dict[str, Any] | None = None,
        pinned_root: bool = False,
    ) -> dict[str, Any]:
        node = nodes.upsert_node(
            self._conn,
            node_type=node_type,
            title=title,
            text=text,
            ref_id=ref_id,
            ref_table=ref_table,
            source=source,
            metadata=metadata,
            pinned_root=pinned_root,
            fts_enabled=self._fts_enabled,
        )
        self._conn.commit()
        return node

    def get_node(self, node_id: str) -> dict[str, Any]:
        return nodes.get_node(self._conn, node_id)

    def update_node(self, node_id: str, **updates: Any) -> dict[str, Any]:
        node = nodes.update_node(
            self._conn,
            node_id,
            title=updates.get("title"),
            text=updates.get("text"),
            metadata=updates.get("metadata"),
            pinned_root=updates.get("pinned_root"),
            fts_enabled=self._fts_enabled,
        )
        self._conn.commit()
        return node

    def delete_node(self, node_id: str) -> bool:
        deleted = nodes.delete_node(
            self._conn, node_id, fts_enabled=self._fts_enabled
        )
        self._conn.commit()
        return deleted

    def list_nodes(
        self,
        *,
        node_type: str | None = None,
        pinned_root: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return nodes.list_nodes(
            self._conn,
            node_type=node_type,
            pinned_root=pinned_root,
            limit=limit,
            offset=offset,
        )

    def pin_root(self, node_id: str, pinned: bool = True) -> dict[str, Any]:
        return self.update_node(node_id, pinned_root=pinned)

    def root_nodes(self, *, limit: int = 25) -> list[dict[str, Any]]:
        return self.list_nodes(pinned_root=True, limit=limit)

    # ------------------------------------------------------------------
    # Edges and traversal
    # ------------------------------------------------------------------

    def create_edge(
        self,
        *,
        source_id: str,
        target_id: str,
        relationship: GraphRelationship | str,
        weight: float = 1.0,
        directed: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        nodes.get_node(self._conn, source_id)
        nodes.get_node(self._conn, target_id)
        edge = edges.create_edge(
            self._conn,
            source_id=source_id,
            target_id=target_id,
            relationship=relationships.relationship_value(relationship),
            weight=weight,
            directed=directed,
            metadata=metadata,
        )
        self._conn.commit()
        return edge

    def list_edges(
        self,
        *,
        node_id: str | None = None,
        relationship: str | None = None,
        direction: str = "both",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return edges.list_edges(
            self._conn,
            node_id=node_id,
            relationship=relationship,
            direction=direction,
            limit=limit,
        )

    def neighbors(
        self,
        node_id: str,
        *,
        max_depth: int = 1,
        relationship: str | None = None,
    ) -> dict[str, Any]:
        return graph_search.traversal(
            self._conn,
            node_id,
            max_depth=max_depth,
            relationship=relationship,
        )

    def traverse(
        self,
        start_node_id: str,
        *,
        max_depth: int = 2,
        relationship: str | None = None,
    ) -> dict[str, Any]:
        return self.neighbors(
            start_node_id,
            max_depth=max_depth,
            relationship=relationship,
        )

    def neighborhood_search(
        self,
        query: str,
        *,
        start_node_id: str | None = None,
        limit: int = 10,
        max_depth: int = 2,
    ) -> list[dict[str, Any]]:
        return graph_search.semantic_neighborhood_search(
            self._conn,
            query,
            start_node_id=start_node_id,
            limit=limit,
            max_depth=max_depth,
            fts_enabled=self._fts_enabled,
        )

    # ------------------------------------------------------------------
    # Relationship integrations
    # ------------------------------------------------------------------

    def ensure_note_node(self, note_id: str) -> dict[str, Any]:
        existing = nodes.get_node_by_ref(self._conn, "vault_notes", note_id)
        if existing:
            return existing
        note = self._load_note(note_id)
        return self.create_node(**relationships.note_node_payload(note))

    def ensure_memory_node(self, memory_id: str) -> dict[str, Any]:
        existing = nodes.get_node_by_ref(self._conn, "memories", memory_id)
        if existing:
            return existing
        memory = self._load_memory(memory_id)
        return self.create_node(**relationships.memory_node_payload(memory))

    def link_notes(
        self,
        source_note_id: str,
        target_note_id: str,
        *,
        relationship: GraphRelationship | str = GraphRelationship.references,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = self.ensure_note_node(source_note_id)
        target = self.ensure_note_node(target_note_id)
        return self.create_edge(
            source_id=source["id"],
            target_id=target["id"],
            relationship=relationship,
            weight=weight,
            metadata={"source": "note_link", **(metadata or {})},
        )

    def link_memory_to_note(
        self,
        memory_id: str,
        note_id: str,
        *,
        relationship: GraphRelationship | str = GraphRelationship.related_to,
        weight: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        memory = self.ensure_memory_node(memory_id)
        note = self.ensure_note_node(note_id)
        return self.create_edge(
            source_id=memory["id"],
            target_id=note["id"],
            relationship=relationship,
            weight=weight,
            metadata={"source": "memory_note_link", **(metadata or {})},
        )

    def link_research_to_source(
        self,
        research_id: str,
        source: dict[str, Any],
        *,
        title: str | None = None,
        summary: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        research = self.create_node(
            node_type=GraphNodeType.research.value,
            title=title or research_id,
            text=summary,
            ref_id=research_id,
            ref_table="research_reports",
            source="research",
            metadata=metadata or {},
        )
        source_node = self.create_node(**relationships.source_node_payload(source))
        return self.create_edge(
            source_id=research["id"],
            target_id=source_node["id"],
            relationship=GraphRelationship.sourced_from,
            metadata={"source": "research_source_link"},
        )

    def add_repo_snapshot(self, summary: dict[str, Any]) -> dict[str, Any]:
        root = str(summary.get("root") or summary.get("git_repository") or "")
        title = root.split("/")[-1] if root else "Repository"
        return self.create_node(
            node_type=GraphNodeType.repo.value,
            title=title,
            text=str(summary.get("detected_stack") or ""),
            ref_id=root,
            ref_table="repo_index_snapshots",
            source="repo_index",
            metadata={
                "root": root,
                "current_branch": summary.get("current_branch", ""),
                "languages": summary.get("languages", {}),
                "local_only": True,
            },
        )

    # ------------------------------------------------------------------
    # Project decisions and timelines
    # ------------------------------------------------------------------

    def record_project_decision(
        self,
        *,
        project_id: str,
        title: str,
        decision: str,
        rationale: str = "",
        status: str = "accepted",
        made_at: str | None = None,
        note_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        project = self.create_node(
            node_type=GraphNodeType.project.value,
            title=project_id,
            ref_id=project_id,
            ref_table="projects",
            source="memory",
            metadata={"project_id": project_id},
        )
        decision_node = self.create_node(
            node_type=GraphNodeType.decision.value,
            title=title,
            text="\n\n".join(part for part in (decision, rationale) if part),
            source="knowledge_graph",
            metadata={"project_id": project_id, "status": status, **(metadata or {})},
        )
        record = decisions.create_decision(
            self._conn,
            node_id=decision_node["id"],
            project_id=project_id,
            title=title,
            decision=decision,
            rationale=rationale,
            status=status,
            made_at=made_at,
            note_id=note_id,
            metadata=metadata,
        )
        self.create_edge(
            source_id=project["id"],
            target_id=decision_node["id"],
            relationship=GraphRelationship.decided,
            metadata={"decision_id": record["id"]},
        )
        if note_id:
            note = self.ensure_note_node(note_id)
            self.create_edge(
                source_id=decision_node["id"],
                target_id=note["id"],
                relationship=GraphRelationship.derived_from,
                metadata={"decision_id": record["id"]},
            )
        self.add_timeline_event(
            node_id=decision_node["id"],
            project_id=project_id,
            event_type="decision",
            title=title,
            summary=decision,
            occurred_at=record["made_at"],
            metadata={"decision_id": record["id"]},
        )
        return record

    def list_project_decisions(
        self,
        *,
        project_id: str | None = None,
        note_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return decisions.list_decisions(
            self._conn, project_id=project_id, note_id=note_id, limit=limit
        )

    def add_timeline_event(
        self,
        *,
        node_id: str | None = None,
        project_id: str | None = None,
        event_type: str = "event",
        title: str,
        summary: str = "",
        occurred_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = timelines.create_event(
            self._conn,
            node_id=node_id,
            project_id=project_id,
            event_type=event_type,
            title=title,
            summary=summary,
            occurred_at=occurred_at,
            metadata=metadata,
        )
        if node_id is None:
            event_node = self.create_node(
                node_type=GraphNodeType.timeline_event.value,
                title=title,
                text=summary,
                source="knowledge_graph",
                metadata={"event_id": event["id"], **(metadata or {})},
            )
            event["node_id"] = event_node["id"]
        self._conn.commit()
        return event

    def list_timeline(
        self,
        *,
        node_id: str | None = None,
        project_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return timelines.list_events(
            self._conn,
            node_id=node_id,
            project_id=project_id,
            event_type=event_type,
            limit=limit,
        )

    def status(self) -> dict[str, Any]:
        row = self._conn.execute("SELECT COUNT(*) AS cnt FROM graph_nodes").fetchone()
        edge = self._conn.execute("SELECT COUNT(*) AS cnt FROM graph_edges").fetchone()
        return {
            "status": "ok",
            "node_count": int(row["cnt"]),
            "edge_count": int(edge["cnt"]),
            "db_path": str(self.db_path),
            "local_only": True,
            "cloud_sync": False,
        }

    def _load_note(self, note_id: str) -> dict[str, Any]:
        if self.vault_service is not None:
            return self.vault_service.get_note(note_id)
        return {
            "id": note_id,
            "title": f"Note {note_id}",
            "content": "",
            "note_type": "note",
            "tags": [],
            "pinned": False,
        }

    def _load_memory(self, memory_id: str) -> dict[str, Any]:
        if self.memory_service is not None:
            return self.memory_service.get_memory(memory_id)
        return {
            "id": memory_id,
            "content": f"Memory {memory_id}",
            "memory_type": "note",
            "tags": [],
            "pinned": False,
            "metadata": {},
        }


def get_knowledge_graph_service(**kwargs: Any) -> KnowledgeGraphService:
    return KnowledgeGraphService(**kwargs)


__all__ = ["KnowledgeGraphService", "get_knowledge_graph_service"]
