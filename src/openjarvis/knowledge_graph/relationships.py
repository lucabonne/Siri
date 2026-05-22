"""Domain relationship helpers for graph integrations."""

from __future__ import annotations

from typing import Any

from openjarvis.knowledge_graph.models import GraphNodeType, GraphRelationship


def note_node_payload(note: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_type": GraphNodeType.note.value,
        "title": note.get("title") or "Untitled note",
        "text": note.get("content") or "",
        "ref_id": note.get("id"),
        "ref_table": "vault_notes",
        "source": "knowledge_vault",
        "metadata": {
            "note_type": note.get("note_type"),
            "tags": note.get("tags") or [],
            "project_id": note.get("project_id"),
            "date": note.get("date"),
        },
        "pinned_root": bool(note.get("pinned")),
    }


def memory_node_payload(memory: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_type": GraphNodeType.memory.value,
        "title": (
            memory.get("metadata", {}).get("title")
            or (memory.get("content") or "")[:80].split("\n")[0]
            or "Memory"
        ),
        "text": memory.get("content") or "",
        "ref_id": memory.get("id"),
        "ref_table": "memories",
        "source": "memory",
        "metadata": {
            "memory_type": memory.get("memory_type"),
            "project_id": memory.get("project_id"),
            "tags": memory.get("tags") or [],
            "source": memory.get("source") or {},
        },
        "pinned_root": bool(memory.get("pinned")),
    }


def source_node_payload(source: dict[str, Any]) -> dict[str, Any]:
    url = source.get("url") or source.get("source_url") or source.get("id") or ""
    return {
        "node_type": GraphNodeType.source.value,
        "title": source.get("title") or source.get("source_name") or url or "Source",
        "text": source.get("summary") or source.get("content") or "",
        "ref_id": source.get("id") or url,
        "ref_table": "sources",
        "source": "research",
        "metadata": {k: v for k, v in source.items() if k not in {"content"}},
    }


def relationship_value(value: GraphRelationship | str) -> str:
    return value.value if isinstance(value, GraphRelationship) else str(value)


__all__ = [
    "note_node_payload",
    "memory_node_payload",
    "source_node_payload",
    "relationship_value",
]
