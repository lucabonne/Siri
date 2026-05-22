"""Structured SQLite memory service for local-first assistant memory."""

from __future__ import annotations

import json
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from openjarvis.memory.semantic import ChromaSemanticIndex


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


class MemoryService:
    """Small service layer over the Phase 1 structured memory database."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        chroma_path: str | Path | None = None,
        enable_semantic: bool = True,
    ) -> None:
        if db_path is None:
            db_path = Path.home() / ".openjarvis" / "siri_memory.db"
        self.db_path = Path(db_path).expanduser()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._fts_enabled = False
        self._create_schema()

        self._semantic: ChromaSemanticIndex | None = None
        if enable_semantic:
            chroma_dir = (
                Path(chroma_path).expanduser()
                if chroma_path is not None
                else Path.home() / ".openjarvis" / "chroma_memory"
            )
            self._semantic = ChromaSemanticIndex(chroma_dir)

    def close(self) -> None:
        self._conn.close()

    def _create_schema(self) -> None:
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                timestamp TEXT NOT NULL DEFAULT '',
                relevance REAL NOT NULL DEFAULT 0,
                tags TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL DEFAULT 'note',
                project_id TEXT,
                source_id TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                tags TEXT NOT NULL DEFAULT '[]',
                pinned INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL,
                FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                due_at TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS research_reports (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL DEFAULT '',
                source_ids TEXT NOT NULL DEFAULT '[]',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS commands_history (
                id TEXT PRIMARY KEY,
                command TEXT NOT NULL,
                cwd TEXT NOT NULL DEFAULT '',
                exit_code INTEGER,
                output_preview TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_runs (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL DEFAULT '',
                task_id TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                input TEXT NOT NULL DEFAULT '',
                output TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                started_at TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS repo_index_snapshots (
                id TEXT PRIMARY KEY,
                repo_root TEXT NOT NULL,
                current_branch TEXT NOT NULL DEFAULT '',
                project_type TEXT NOT NULL DEFAULT 'unknown',
                detected_stack TEXT NOT NULL DEFAULT '{}',
                architecture_metadata TEXT NOT NULL DEFAULT '{}',
                summary TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_briefings (
                id TEXT PRIMARY KEY,
                briefing_date TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS morning_events (
                id TEXT PRIMARY KEY,
                briefing_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'world',
                summary TEXT NOT NULL DEFAULT '',
                latitude REAL,
                longitude REAL,
                location_name TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                source_name TEXT NOT NULL DEFAULT '',
                published_at TEXT NOT NULL DEFAULT '',
                importance INTEGER NOT NULL DEFAULT 3,
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id);
            CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
            CREATE INDEX IF NOT EXISTS idx_memories_pinned ON memories(pinned);
            CREATE INDEX IF NOT EXISTS idx_repo_index_root
            ON repo_index_snapshots(repo_root);
            CREATE INDEX IF NOT EXISTS idx_morning_events_briefing
            ON morning_events(briefing_id);
            CREATE INDEX IF NOT EXISTS idx_morning_events_category
            ON morning_events(category);
            """
        )
        try:
            self._conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                USING fts5(id UNINDEXED, content, tags, metadata)
                """
            )
            self._fts_enabled = True
        except sqlite3.Error:
            self._fts_enabled = False
        self._conn.commit()

    def create_memory(
        self,
        content: str,
        *,
        memory_type: str = "note",
        project_id: str | None = None,
        source: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        pinned: bool = False,
    ) -> dict[str, Any]:
        if not content.strip():
            raise ValueError("memory content cannot be empty")

        now = _utc_now()
        if project_id:
            self._ensure_project(project_id)
        source_id = self._create_source(source) if source else None
        memory_id = str(uuid.uuid4())
        self._conn.execute(
            """
            INSERT INTO memories (
                id, content, memory_type, project_id, source_id, metadata,
                tags, pinned, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                content,
                memory_type or "note",
                project_id,
                source_id,
                _json_dumps(metadata),
                _json_dumps(tags or []),
                1 if pinned else 0,
                now,
                now,
            ),
        )
        self._upsert_fts(memory_id, content, tags or [], metadata or {})
        self._conn.commit()
        memory = self.get_memory(memory_id)
        if self._semantic is not None:
            self._semantic.upsert(
                memory_id,
                content,
                {
                    "memory_type": memory_type or "note",
                    "project_id": project_id or "",
                    "created_at": now,
                },
            )
        return memory

    def _ensure_project(self, project_id: str) -> None:
        now = _utc_now()
        self._conn.execute(
            """
            INSERT OR IGNORE INTO projects (
                id, name, description, status, metadata, created_at, updated_at
            )
            VALUES (?, ?, '', 'active', '{}', ?, ?)
            """,
            (project_id, project_id, now, now),
        )

    def _create_source(self, source: dict[str, Any]) -> str:
        source_id = source.get("id") or str(uuid.uuid4())
        tags = source.get("tags") or []
        self._conn.execute(
            """
            INSERT OR REPLACE INTO sources (
                id, title, url, timestamp, relevance, tags, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                source.get("title") or "",
                source.get("url") or "",
                source.get("timestamp") or _utc_now(),
                float(source.get("relevance") or 0),
                _json_dumps(tags),
                _utc_now(),
            ),
        )
        return source_id

    def get_memory(
        self,
        memory_id: str,
        *,
        score: float | None = None,
    ) -> dict[str, Any]:
        row = self._conn.execute(
            """
            SELECT m.*, s.title AS source_title, s.url AS source_url,
                   s.timestamp AS source_timestamp, s.relevance AS source_relevance,
                   s.tags AS source_tags
            FROM memories m
            LEFT JOIN sources s ON s.id = m.source_id
            WHERE m.id = ?
            """,
            (memory_id,),
        ).fetchone()
        if row is None:
            raise KeyError(memory_id)
        return self._row_to_memory(row, score=score)

    def list_memories(
        self,
        *,
        project_id: str | None = None,
        memory_type: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        pinned: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql, params = self._filtered_select(
            project_id=project_id,
            memory_type=memory_type,
            created_after=created_after,
            created_before=created_before,
            pinned=pinned,
        )
        sql += " ORDER BY m.pinned DESC, m.created_at DESC LIMIT ? OFFSET ?"
        params.extend([max(1, min(limit, 200)), max(0, offset)])
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def search_memories(
        self,
        query: str,
        *,
        project_id: str | None = None,
        memory_type: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        pinned: bool | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            return self.list_memories(
                project_id=project_id,
                memory_type=memory_type,
                created_after=created_after,
                created_before=created_before,
                pinned=pinned,
                limit=limit,
            )

        semantic = self._semantic_results(query, limit, project_id, memory_type)
        if semantic:
            self._apply_memory_weights(semantic)
            semantic.sort(key=lambda x: x.get("score", 0), reverse=True)
            return semantic

        if self._fts_enabled:
            rows = self._search_fts(
                query,
                project_id=project_id,
                memory_type=memory_type,
                created_after=created_after,
                created_before=created_before,
                pinned=pinned,
                limit=limit,
            )
        else:
            rows = self._search_like(
                query,
                project_id=project_id,
                memory_type=memory_type,
                created_after=created_after,
                created_before=created_before,
                pinned=pinned,
                limit=limit,
            )
        
        results = [self._row_to_memory(row, score=row["score"]) for row in rows]
        self._apply_memory_weights(results)
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results

    def _apply_memory_weights(self, items: list[dict[str, Any]]) -> None:
        try:
            from openjarvis.personalization.memory_weights import get_weight_for_memory_type
            for item in items:
                m_type = item.get("memory_type", "note")
                weight = get_weight_for_memory_type(m_type)
                if "score" in item:
                    item["score"] *= weight
        except ImportError:
            pass

    def delete_memory(self, memory_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        if self._fts_enabled:
            self._conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
        self._conn.commit()
        if self._semantic is not None:
            self._semantic.delete(memory_id)
        return cur.rowcount > 0

    def set_pinned(self, memory_id: str, pinned: bool) -> dict[str, Any]:
        now = _utc_now()
        cur = self._conn.execute(
            "UPDATE memories SET pinned = ?, updated_at = ? WHERE id = ?",
            (1 if pinned else 0, now, memory_id),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            raise KeyError(memory_id)
        return self.get_memory(memory_id)

    def record_command_history(
        self,
        *,
        command: str,
        cwd: str = "",
        exit_code: int | None = None,
        output_preview: str = "",
        metadata: dict[str, Any] | None = None,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        """Persist a passive terminal command summary in structured memory."""
        if not command.strip():
            raise ValueError("command cannot be empty")
        command_id = str(uuid.uuid4())
        created = created_at or _utc_now()
        self._conn.execute(
            """
            INSERT INTO commands_history (
                id, command, cwd, exit_code, output_preview, metadata, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command_id,
                command,
                cwd,
                exit_code,
                output_preview,
                _json_dumps(metadata or {}),
                created,
            ),
        )
        self._conn.commit()
        return self.get_command_history(command_id)

    def get_command_history(self, command_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM commands_history WHERE id = ?",
            (command_id,),
        ).fetchone()
        if row is None:
            raise KeyError(command_id)
        return self._row_to_command_history(row)

    def list_command_history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM commands_history
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()
        return [self._row_to_command_history(row) for row in rows]

    def record_repo_index_summary(self, summary: dict[str, Any]) -> dict[str, Any]:
        """Persist a local repo indexing snapshot for memory-aware context.

        This stores metadata and summaries only; file contents are not copied
        into the memory database.
        """
        repo_root = str(summary.get("root") or summary.get("git_repository") or "")
        if not repo_root.strip():
            raise ValueError("repo root cannot be empty")
        snapshot_id = str(uuid.uuid4())
        detected_stack = summary.get("detected_stack") or {}
        architecture = summary.get("architecture") or {}
        architecture_metadata = architecture.get("metadata", {})
        now = _utc_now()
        self._conn.execute(
            """
            INSERT INTO repo_index_snapshots (
                id, repo_root, current_branch, project_type, detected_stack,
                architecture_metadata, summary, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                repo_root,
                str(summary.get("current_branch") or ""),
                str(detected_stack.get("project_type") or "unknown"),
                _json_dumps(detected_stack),
                _json_dumps(architecture_metadata),
                _json_dumps(
                    {
                        "file_count": summary.get("file_count", 0),
                        "indexed_file_count": summary.get("indexed_file_count", 0),
                        "languages": summary.get("languages", {}),
                        "local_only": True,
                        "passive_only": True,
                    }
                ),
                now,
            ),
        )
        self._conn.commit()
        return self.get_repo_index_snapshot(snapshot_id)

    def get_repo_index_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM repo_index_snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise KeyError(snapshot_id)
        return self._row_to_repo_index_snapshot(row)

    def list_repo_index_snapshots(
        self,
        *,
        repo_root: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM repo_index_snapshots WHERE 1 = 1"
        params: list[Any] = []
        if repo_root:
            sql += " AND repo_root = ?"
            params.append(repo_root)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 100)))
        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_repo_index_snapshot(row) for row in rows]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS count FROM memories").fetchone()
        return int(row["count"])

    def semantic_status(self) -> dict[str, Any]:
        if self._semantic is None:
            return {"enabled": False, "backend": "disabled", "error": ""}
        return self._semantic.status()

    def _filtered_select(self, **filters: Any) -> tuple[str, list[Any]]:
        sql = """
            SELECT m.*, s.title AS source_title, s.url AS source_url,
                   s.timestamp AS source_timestamp, s.relevance AS source_relevance,
                   s.tags AS source_tags
            FROM memories m
            LEFT JOIN sources s ON s.id = m.source_id
            WHERE 1 = 1
        """
        params: list[Any] = []
        sql, params = self._append_filters(sql, params, **filters)
        return sql, params

    def _append_filters(
        self,
        sql: str,
        params: list[Any],
        **filters: Any,
    ) -> tuple[str, list[Any]]:
        if filters.get("project_id"):
            sql += " AND m.project_id = ?"
            params.append(filters["project_id"])
        if filters.get("memory_type"):
            sql += " AND m.memory_type = ?"
            params.append(filters["memory_type"])
        if filters.get("created_after"):
            sql += " AND m.created_at >= ?"
            params.append(filters["created_after"])
        if filters.get("created_before"):
            sql += " AND m.created_at <= ?"
            params.append(filters["created_before"])
        if filters.get("pinned") is not None:
            sql += " AND m.pinned = ?"
            params.append(1 if filters["pinned"] else 0)
        return sql, params

    def _search_fts(self, query: str, limit: int, **filters: Any) -> list[sqlite3.Row]:
        tokens = re.findall(r"[\w]+", query)
        fts_query = " OR ".join(tokens) if tokens else query
        sql = """
            SELECT m.*, s.title AS source_title, s.url AS source_url,
                   s.timestamp AS source_timestamp, s.relevance AS source_relevance,
                   s.tags AS source_tags, bm25(memories_fts) * -1 AS score
            FROM memories_fts
            JOIN memories m ON m.id = memories_fts.id
            LEFT JOIN sources s ON s.id = m.source_id
            WHERE memories_fts MATCH ?
        """
        params: list[Any] = [fts_query]
        sql, params = self._append_filters(sql, params, **filters)
        sql += " ORDER BY score DESC, m.pinned DESC, m.created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 50)))
        try:
            return list(self._conn.execute(sql, params).fetchall())
        except sqlite3.Error:
            return self._search_like(query, limit, **filters)

    def _search_like(self, query: str, limit: int, **filters: Any) -> list[sqlite3.Row]:
        sql = """
            SELECT m.*, s.title AS source_title, s.url AS source_url,
                   s.timestamp AS source_timestamp, s.relevance AS source_relevance,
                   s.tags AS source_tags,
                   CASE
                       WHEN lower(m.content) LIKE lower(?) THEN 1.0
                       ELSE 0.1
                   END AS score
            FROM memories m
            LEFT JOIN sources s ON s.id = m.source_id
            WHERE (lower(m.content) LIKE lower(?) OR lower(m.tags) LIKE lower(?)
                   OR lower(m.metadata) LIKE lower(?))
        """
        like = f"%{query}%"
        params: list[Any] = [like, like, like, like]
        sql, params = self._append_filters(sql, params, **filters)
        sql += " ORDER BY score DESC, m.pinned DESC, m.created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 50)))
        return list(self._conn.execute(sql, params).fetchall())

    def _semantic_results(
        self,
        query: str,
        limit: int,
        project_id: str | None,
        memory_type: str | None,
    ) -> list[dict[str, Any]]:
        if self._semantic is None or not self._semantic.available:
            return []
        matches = self._semantic.query(query, limit=max(limit * 2, limit))
        items: list[dict[str, Any]] = []
        for match in matches:
            try:
                memory = self.get_memory(match["id"], score=match["score"])
            except KeyError:
                continue
            if project_id and memory["project_id"] != project_id:
                continue
            if memory_type and memory["memory_type"] != memory_type:
                continue
            items.append(memory)
            if len(items) >= limit:
                break
        return items

    def _upsert_fts(
        self,
        memory_id: str,
        content: str,
        tags: list[str],
        metadata: dict[str, Any],
    ) -> None:
        if not self._fts_enabled:
            return
        self._conn.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
        self._conn.execute(
            """
            INSERT INTO memories_fts (id, content, tags, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (memory_id, content, " ".join(tags), _json_dumps(metadata)),
        )

    def _row_to_memory(
        self,
        row: sqlite3.Row,
        *,
        score: float | None = None,
    ) -> dict[str, Any]:
        source = None
        if row["source_id"]:
            source = {
                "id": row["source_id"],
                "title": row["source_title"] or "",
                "url": row["source_url"] or "",
                "timestamp": row["source_timestamp"] or "",
                "relevance": float(row["source_relevance"] or 0),
                "tags": _json_loads(row["source_tags"], []),
            }
        item = {
            "id": row["id"],
            "content": row["content"],
            "memory_type": row["memory_type"],
            "project_id": row["project_id"],
            "source": source,
            "metadata": _json_loads(row["metadata"], {}),
            "tags": _json_loads(row["tags"], []),
            "pinned": bool(row["pinned"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        if score is not None:
            item["score"] = float(score)
        return item

    @staticmethod
    def _row_to_command_history(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "command": row["command"],
            "cwd": row["cwd"],
            "exit_code": row["exit_code"],
            "output_preview": row["output_preview"],
            "metadata": _json_loads(row["metadata"], {}),
            "created_at": row["created_at"],
        }

    @staticmethod
    def _row_to_repo_index_snapshot(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "repo_root": row["repo_root"],
            "current_branch": row["current_branch"],
            "project_type": row["project_type"],
            "detected_stack": _json_loads(row["detected_stack"], {}),
            "architecture_metadata": _json_loads(row["architecture_metadata"], {}),
            "summary": _json_loads(row["summary"], {}),
            "created_at": row["created_at"],
            "local_only": True,
            "passive_only": True,
        }


__all__ = ["MemoryService"]
