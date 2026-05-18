"""Claim extraction for source-backed research notes."""

from __future__ import annotations

import re

from openjarvis.research.models import ResearchPlan, ResearchSource


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return []
    chunks = re.split(r"(?<=[.!?])\s+", cleaned)
    return [chunk.strip() for chunk in chunks if len(chunk.strip()) > 24]


def _terms(plan: ResearchPlan) -> set[str]:
    text = " ".join([plan.question, *plan.subtopics]).lower()
    return {
        word
        for word in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text)
        if word not in {"and", "the", "for", "with", "from"}
    }


class ClaimExtractor:
    """Extract concise claims from cached source snippets."""

    def extract(
        self,
        sources: list[ResearchSource],
        plan: ResearchPlan,
        *,
        max_claims_per_source: int = 3,
    ) -> list[ResearchSource]:
        terms = _terms(plan)
        enriched: list[ResearchSource] = []
        for source in sources:
            candidates = _sentences(source.snippet) or [source.title]
            scored: list[tuple[int, str]] = []
            for sentence in candidates:
                lower = sentence.lower()
                score = sum(1 for term in terms if term in lower)
                scored.append((score, sentence))
            scored.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
            claims = [
                sentence
                for score, sentence in scored
                if score > 0 or not terms
            ][:max_claims_per_source]
            if not claims and candidates:
                claims = candidates[:1]
            source.extracted_claims = claims
            if claims:
                source.relevance = max(
                    source.relevance,
                    min(1.0, 0.25 + 0.2 * len(claims)),
                )
            enriched.append(source)
        return enriched


__all__ = ["ClaimExtractor"]
