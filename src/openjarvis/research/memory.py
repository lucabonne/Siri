"""Memory integration for research sessions."""

from __future__ import annotations

from typing import Any

from openjarvis.research.models import ResearchReport, ResearchSource


class ResearchMemoryWriter:
    """Persist research artifacts to the structured local memory service."""

    def write(
        self,
        *,
        memory_service: Any,
        report: ResearchReport,
        sources: list[ResearchSource],
        privacy_mode: bool,
    ) -> list[str]:
        if memory_service is None:
            return []
        memory_ids: list[str] = []
        try:
            memory = memory_service.create_memory(
                report.summary,
                memory_type="research_report",
                source=(
                    {
                        "title": report.citations[0].title,
                        "url": report.citations[0].url,
                        "timestamp": report.created_at,
                        "relevance": report.citations[0].relevance,
                        "tags": ["research"],
                    }
                    if report.citations
                    else None
                ),
                metadata={
                    "research_id": report.id,
                    "question": report.question,
                    "citation_count": len(report.citations),
                    "source_count": len(sources),
                    "privacy_mode": privacy_mode,
                    "local_only": True,
                    "cloud_persistence": False,
                    "passive_only": True,
                },
                tags=["research", "autonomous-research-phase-1"],
            )
            memory_ids.append(str(memory["id"]))
        except Exception:
            return memory_ids

        for source in sources[:8]:
            if not source.extracted_claims:
                continue
            try:
                memory = memory_service.create_memory(
                    "\n".join(source.extracted_claims),
                    memory_type="research_source",
                    source={
                        "title": source.title,
                        "url": source.url,
                        "timestamp": source.access_date,
                        "relevance": source.relevance,
                        "tags": ["research-source", source.source_type],
                    },
                    metadata={
                        "research_id": report.id,
                        "source_id": source.id,
                        "source_type": source.source_type,
                        "privacy_mode": privacy_mode,
                        "local_only": True,
                        "cloud_persistence": False,
                        "passive_only": True,
                    },
                    tags=["research-source", "research"],
                )
                memory_ids.append(str(memory["id"]))
            except Exception:
                continue
        return memory_ids


__all__ = ["ResearchMemoryWriter"]
