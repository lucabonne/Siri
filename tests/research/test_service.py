from __future__ import annotations

from pathlib import Path

from openjarvis.memory import MemoryService
from openjarvis.research import ResearchService


def _memory(tmp_path: Path) -> MemoryService:
    return MemoryService(
        db_path=tmp_path / "memory.db",
        chroma_path=tmp_path / "chroma",
        enable_semantic=False,
    )


def test_research_service_runs_one_shot_workflow_and_stores_memory(tmp_path: Path):
    memory = _memory(tmp_path)
    service = ResearchService(
        db_path=tmp_path / "research.db",
        memory_service=memory,
    )
    try:
        session = service.start_research(
            "How should Siri handle local-first research?",
            seed_sources=[
                {
                    "title": "Local research design",
                    "url": "https://example.test/local-research",
                    "content": (
                        "Siri local-first research should collect cached sources "
                        "before summary generation. Reports should include citations."
                    ),
                    "relevance": 0.9,
                }
            ],
        )

        assert session.status == "completed"
        assert session.plan.question == "How should Siri handle local-first research?"
        assert session.plan.search_strategy
        assert session.sources[0].title == "Local research design"
        assert session.sources[0].extracted_claims
        assert session.report is not None
        assert session.report.citations[0].label == "[1]"
        assert "## Unresolved Questions" in session.report.body
        assert session.memory_ids

        stored = service.get_session(session.id)
        assert stored.report is not None
        assert stored.report.summary == session.report.summary
        assert service.status(session.id)["source_count"] == 1
        assert service.memory_entries(session.id)
    finally:
        service.close()
        memory.close()


def test_research_privacy_mode_forces_cached_sources_only(tmp_path: Path):
    service = ResearchService(db_path=tmp_path / "research.db")
    try:
        session = service.start_research(
            "Privacy research",
            seed_sources=[
                {
                    "title": "Cached note",
                    "content": "Privacy Mode should use cached sources only.",
                }
            ],
            allow_external_search=True,
            privacy_mode=True,
        )

        assert session.privacy_mode is True
        assert session.cached_sources_only is True
        assert session.local_only is True
        assert session.passive_only is True
        assert all(
            source.source_type != "external_search" for source in session.sources
        )
        assert session.report is not None
        assert session.report.metadata["notifications"] is False
        assert session.report.metadata["background_agents"] is False
    finally:
        service.close()
