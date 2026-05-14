"""Tests for the Phase 1 structured memory service."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from openjarvis.memory import MemoryService


def _service(tmp_path: Path) -> MemoryService:
    return MemoryService(
        db_path=tmp_path / "memory.db",
        chroma_path=tmp_path / "chroma",
        enable_semantic=False,
    )


def test_structured_schema_creates_phase1_tables(tmp_path: Path):
    service = _service(tmp_path)
    try:
        conn = sqlite3.connect(tmp_path / "memory.db")
        tables = {
            row[0]
            for row in conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type IN ('table', 'virtual table')
                """
            )
        }
        assert {
            "memories",
            "projects",
            "tasks",
            "sources",
            "research_reports",
            "commands_history",
            "agent_runs",
            "daily_briefings",
        }.issubset(tables)
    finally:
        service.close()


def test_create_search_filter_pin_and_delete_memory(tmp_path: Path):
    service = _service(tmp_path)
    try:
        first = service.create_memory(
            "Siri should remember the mission control API decision",
            memory_type="decision",
            project_id="mission-control",
            tags=["api", "memory"],
            source={
                "title": "Design note",
                "url": "https://example.test/design",
                "timestamp": "2026-05-14T08:00:00Z",
                "relevance": 0.9,
                "tags": ["design"],
            },
        )
        service.create_memory(
            "Unrelated note about local setup",
            memory_type="note",
            project_id="setup",
        )

        results = service.search_memories(
            "mission control",
            project_id="mission-control",
            memory_type="decision",
        )

        assert [item["id"] for item in results] == [first["id"]]
        assert results[0]["source"]["title"] == "Design note"
        assert results[0]["source"]["url"] == "https://example.test/design"
        assert results[0]["source"]["relevance"] == 0.9

        pinned = service.set_pinned(first["id"], True)
        assert pinned["pinned"] is True
        assert service.list_memories(pinned=True)[0]["id"] == first["id"]

        assert service.delete_memory(first["id"]) is True
        assert service.delete_memory(first["id"]) is False
    finally:
        service.close()


def test_empty_search_lists_filtered_memories(tmp_path: Path):
    service = _service(tmp_path)
    try:
        service.create_memory("A project note", memory_type="note", project_id="alpha")
        service.create_memory(
            "Another project note",
            memory_type="note",
            project_id="beta",
        )

        results = service.search_memories("", project_id="alpha")

        assert len(results) == 1
        assert results[0]["project_id"] == "alpha"
    finally:
        service.close()
