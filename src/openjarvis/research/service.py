"""Coordinating service for Autonomous Research Mode Phase 1."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from openjarvis.research.citations import CitationGenerator
from openjarvis.research.extraction import ClaimExtractor
from openjarvis.research.memory import ResearchMemoryWriter
from openjarvis.research.models import (
    Citation,
    ResearchPlan,
    ResearchReport,
    ResearchSession,
    ResearchSource,
)
from openjarvis.research.planner import ResearchPlanner
from openjarvis.research.report import ResearchReportBuilder
from openjarvis.research.search import SourceSearch
from openjarvis.research.summarizer import ResearchSummarizer


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


class ResearchService:
    """Run explicit one-shot research workflows and cache their artifacts."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        memory_service: Any = None,
        worldmonitor_service: Any = None,
        morning_briefing_service: Any = None,
        planner: ResearchPlanner | None = None,
        searcher: SourceSearch | None = None,
        extractor: ClaimExtractor | None = None,
        citation_generator: CitationGenerator | None = None,
        summarizer: ResearchSummarizer | None = None,
        report_builder: ResearchReportBuilder | None = None,
        memory_writer: ResearchMemoryWriter | None = None,
    ) -> None:
        if db_path is None:
            db_path = Path.home() / ".openjarvis" / "siri_memory.db"
        self.db_path = Path(db_path).expanduser()
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._memory_service = memory_service
        self._worldmonitor_service = worldmonitor_service
        self._morning_briefing_service = morning_briefing_service
        self._planner = planner or ResearchPlanner()
        self._searcher = searcher or SourceSearch()
        self._extractor = extractor or ClaimExtractor()
        self._citation_generator = citation_generator or CitationGenerator()
        self._summarizer = summarizer or ResearchSummarizer()
        self._report_builder = report_builder or ResearchReportBuilder()
        self._memory_writer = memory_writer or ResearchMemoryWriter()
        self._create_schema()

    def close(self) -> None:
        self._conn.close()

    def _create_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS research_sessions (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                status TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT '{}',
                report TEXT NOT NULL DEFAULT '{}',
                memory_ids TEXT NOT NULL DEFAULT '[]',
                privacy_mode INTEGER NOT NULL DEFAULT 0,
                cached_sources_only INTEGER NOT NULL DEFAULT 1,
                local_only INTEGER NOT NULL DEFAULT 1,
                passive_only INTEGER NOT NULL DEFAULT 1,
                active_mode_id TEXT NOT NULL DEFAULT '',
                workspace_agent_id TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS research_sources (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                access_date TEXT NOT NULL DEFAULT '',
                relevance REAL NOT NULL DEFAULT 0,
                extracted_claims TEXT NOT NULL DEFAULT '[]',
                snippet TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT 'cached',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES research_sessions(id)
                ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_research_sessions_created
            ON research_sessions(created_at);
            CREATE INDEX IF NOT EXISTS idx_research_sources_session
            ON research_sources(session_id);
            """
        )
        self._conn.commit()

    def start_research(
        self,
        question: str,
        *,
        seed_sources: list[dict[str, Any]] | None = None,
        allow_external_search: bool = False,
        privacy_mode: bool = False,
        active_mode_id: str = "",
        workspace_agent_id: str = "",
        max_sources: int = 8,
    ) -> ResearchSession:
        plan = self._planner.plan(question)
        session_id = str(uuid.uuid4())
        cached_only = privacy_mode or not allow_external_search

        sources = self._searcher.collect(
            plan=plan,
            memory_service=self._memory_service,
            worldmonitor_service=self._worldmonitor_service,
            morning_briefing_service=self._morning_briefing_service,
            seed_sources=seed_sources,
            allow_external_search=allow_external_search,
            privacy_mode=privacy_mode,
            max_sources=max_sources,
        )
        sources = self._extractor.extract(sources, plan)
        citations = self._citation_generator.generate(sources)
        summary, notes, unresolved = self._summarizer.summarize(
            plan=plan,
            sources=sources,
            citations=citations,
        )
        report = self._report_builder.build(
            report_id=session_id,
            question=plan.question,
            summary=summary,
            notes=notes,
            citations=citations,
            unresolved_questions=unresolved,
            metadata={
                "privacy_mode": privacy_mode,
                "cached_sources_only": cached_only,
                "local_only": True,
                "passive_only": True,
                "notifications": False,
                "background_agents": False,
                "external_search_requested": allow_external_search,
                "external_search_used": any(
                    source.source_type == "external_search" for source in sources
                ),
            },
        )
        memory_ids = self._memory_writer.write(
            memory_service=self._memory_service,
            report=report,
            sources=sources,
            privacy_mode=privacy_mode,
        )
        session = ResearchSession(
            id=session_id,
            question=plan.question,
            status="completed",
            plan=plan,
            sources=sources,
            report=report,
            memory_ids=memory_ids,
            privacy_mode=privacy_mode,
            cached_sources_only=cached_only,
            local_only=True,
            passive_only=True,
            active_mode_id=active_mode_id,
            workspace_agent_id=workspace_agent_id,
            created_at=report.created_at,
            updated_at=report.created_at,
            metadata={
                "source_count": len(sources),
                "citation_count": len(citations),
                "memory_count": len(memory_ids),
            },
        )
        self._store_session(session)
        return session

    def list_sessions(self, *, limit: int = 20) -> list[ResearchSession]:
        rows = self._conn.execute(
            """
            SELECT * FROM research_sessions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, min(limit, 100)),),
        ).fetchall()
        return [self._row_to_session(row) for row in rows]

    def get_session(self, research_id: str) -> ResearchSession:
        row = self._conn.execute(
            "SELECT * FROM research_sessions WHERE id = ?",
            (research_id,),
        ).fetchone()
        if row is None:
            raise KeyError(research_id)
        return self._row_to_session(row)

    def status(self, research_id: str) -> dict[str, Any]:
        session = self.get_session(research_id)
        return {
            "id": session.id,
            "question": session.question,
            "status": session.status,
            "source_count": len(session.sources),
            "citation_count": len(session.report.citations) if session.report else 0,
            "memory_count": len(session.memory_ids),
            "privacy_mode": session.privacy_mode,
            "cached_sources_only": session.cached_sources_only,
            "local_only": session.local_only,
            "passive_only": session.passive_only,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    def memory_entries(self, research_id: str) -> list[dict[str, Any]]:
        session = self.get_session(research_id)
        if self._memory_service is None:
            return []
        entries: list[dict[str, Any]] = []
        for memory_id in session.memory_ids:
            try:
                entries.append(self._memory_service.get_memory(memory_id))
            except Exception:
                continue
        return entries

    def _store_session(self, session: ResearchSession) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO research_sessions (
                    id, question, status, plan, report, memory_ids, privacy_mode,
                    cached_sources_only, local_only, passive_only, active_mode_id,
                    workspace_agent_id, metadata, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.question,
                    session.status,
                    _json_dumps(session.plan.to_dict()),
                    _json_dumps(session.report.to_dict() if session.report else {}),
                    _json_dumps(session.memory_ids),
                    1 if session.privacy_mode else 0,
                    1 if session.cached_sources_only else 0,
                    1,
                    1,
                    session.active_mode_id,
                    session.workspace_agent_id,
                    _json_dumps(session.metadata),
                    session.created_at,
                    session.updated_at,
                ),
            )
            self._conn.execute(
                "DELETE FROM research_sources WHERE session_id = ?",
                (session.id,),
            )
            for source in session.sources:
                self._conn.execute(
                    """
                    INSERT INTO research_sources (
                        id, session_id, title, url, access_date, relevance,
                        extracted_claims, snippet, source_type, metadata, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source.id,
                        session.id,
                        source.title,
                        source.url,
                        source.access_date,
                        source.relevance,
                        _json_dumps(source.extracted_claims),
                        source.snippet,
                        source.source_type,
                        _json_dumps(source.metadata),
                        session.created_at,
                    ),
                )

    def _row_to_session(self, row: sqlite3.Row) -> ResearchSession:
        plan_data = _json_loads(row["plan"], {})
        report_data = _json_loads(row["report"], {})
        plan = ResearchPlan(
            question=str(plan_data.get("question") or row["question"]),
            search_strategy=list(plan_data.get("search_strategy") or []),
            subtopics=list(plan_data.get("subtopics") or []),
            open_questions=list(plan_data.get("open_questions") or []),
            created_at=str(plan_data.get("created_at") or row["created_at"]),
        )
        citations = [
            Citation(
                id=str(item.get("id", "")),
                source_id=str(item.get("source_id", "")),
                label=str(item.get("label", "")),
                title=str(item.get("title", "")),
                url=str(item.get("url", "")),
                access_date=str(item.get("access_date", "")),
                relevance=float(item.get("relevance") or 0),
            )
            for item in report_data.get("citations", [])
        ]
        report = None
        if report_data:
            report = ResearchReport(
                id=str(report_data.get("id") or row["id"]),
                question=str(report_data.get("question") or row["question"]),
                title=str(report_data.get("title") or ""),
                notes=list(report_data.get("notes") or []),
                summary=str(report_data.get("summary") or ""),
                citations=citations,
                unresolved_questions=list(
                    report_data.get("unresolved_questions") or []
                ),
                body=str(report_data.get("body") or ""),
                created_at=str(report_data.get("created_at") or row["created_at"]),
                metadata=dict(report_data.get("metadata") or {}),
            )
        return ResearchSession(
            id=row["id"],
            question=row["question"],
            status=row["status"],
            plan=plan,
            sources=self._sources_for_session(row["id"]),
            report=report,
            memory_ids=list(_json_loads(row["memory_ids"], [])),
            privacy_mode=bool(row["privacy_mode"]),
            cached_sources_only=bool(row["cached_sources_only"]),
            local_only=bool(row["local_only"]),
            passive_only=bool(row["passive_only"]),
            active_mode_id=row["active_mode_id"],
            workspace_agent_id=row["workspace_agent_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            metadata=dict(_json_loads(row["metadata"], {})),
        )

    def _sources_for_session(self, session_id: str) -> list[ResearchSource]:
        rows = self._conn.execute(
            """
            SELECT * FROM research_sources
            WHERE session_id = ?
            ORDER BY relevance DESC, created_at DESC
            """,
            (session_id,),
        ).fetchall()
        return [
            ResearchSource(
                id=row["id"],
                title=row["title"],
                url=row["url"],
                access_date=row["access_date"],
                relevance=float(row["relevance"] or 0),
                extracted_claims=list(_json_loads(row["extracted_claims"], [])),
                snippet=row["snippet"],
                source_type=row["source_type"],
                metadata=dict(_json_loads(row["metadata"], {})),
            )
            for row in rows
        ]


__all__ = ["ResearchService"]
