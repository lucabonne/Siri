"""Deterministic research summarization."""

from __future__ import annotations

from openjarvis.research.models import Citation, ResearchPlan, ResearchSource


class ResearchSummarizer:
    """Build concise summaries from extracted source claims."""

    def summarize(
        self,
        *,
        plan: ResearchPlan,
        sources: list[ResearchSource],
        citations: list[Citation],
    ) -> tuple[str, list[str], list[str]]:
        claims: list[str] = []
        citation_by_source = {
            citation.source_id: citation.label for citation in citations
        }
        for source in sources:
            label = citation_by_source.get(source.id, "")
            for claim in source.extracted_claims:
                claims.append(f"{claim} {label}".strip())

        notes = claims[:8]
        if notes:
            summary = " ".join(notes[:3])
        else:
            summary = (
                "No source-backed claims were found in the local cache for this "
                "question yet."
            )

        unresolved = list(plan.open_questions)
        if not sources:
            unresolved.insert(0, "No cached sources matched the research question.")
        elif not claims:
            unresolved.insert(0, "Matched sources did not contain extractable claims.")
        return summary, notes, unresolved


__all__ = ["ResearchSummarizer"]
