"""Citation generation for research reports."""

from __future__ import annotations

from openjarvis.research.models import Citation, ResearchSource


class CitationGenerator:
    """Create stable numbered citations from collected sources."""

    def generate(self, sources: list[ResearchSource]) -> list[Citation]:
        citations: list[Citation] = []
        for index, source in enumerate(sources, start=1):
            if not source.url and not source.title:
                continue
            citations.append(
                Citation(
                    id=f"cite-{index}",
                    source_id=source.id,
                    label=f"[{index}]",
                    title=source.title or "Untitled source",
                    url=source.url,
                    access_date=source.access_date,
                    relevance=source.relevance,
                )
            )
        return citations


__all__ = ["CitationGenerator"]
