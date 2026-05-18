"""Research planning for Siri Autonomous Research Mode Phase 1."""

from __future__ import annotations

import re
import time

from openjarvis.research.models import ResearchPlan


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _keywords(question: str) -> list[str]:
    stopwords = {
        "about",
        "after",
        "also",
        "and",
        "are",
        "can",
        "compare",
        "does",
        "for",
        "from",
        "how",
        "into",
        "latest",
        "research",
        "should",
        "that",
        "the",
        "their",
        "this",
        "what",
        "when",
        "where",
        "which",
        "with",
        "would",
    }
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", question.lower())
    seen: set[str] = set()
    result: list[str] = []
    for word in words:
        if word in stopwords or word in seen:
            continue
        seen.add(word)
        result.append(word)
    return result[:6]


class ResearchPlanner:
    """Create a deterministic local-first research plan from a question."""

    def plan(self, question: str) -> ResearchPlan:
        cleaned = re.sub(r"\s+", " ", question).strip()
        if not cleaned:
            raise ValueError("research question cannot be empty")

        keywords = _keywords(cleaned)
        subtopics = self._subtopics(cleaned, keywords)
        search_strategy = [
            f"Search local memory and cached sources for: {cleaned}",
            (
                "Prefer source-backed memories, cached Morning Briefing events, "
                "and WorldMonitor imports."
            ),
            (
                "Extract claims before summarizing; keep source links attached "
                "to every claim."
            ),
        ]
        if keywords:
            search_strategy.append(
                "Use keyword expansion: " + ", ".join(keywords)
            )

        open_questions = [
            f"What evidence is missing for {topic}?" for topic in subtopics[:4]
        ]
        if not open_questions:
            open_questions = [
                "Which source-backed facts are still missing?",
                "What needs confirmation from newer or primary sources?",
            ]

        return ResearchPlan(
            question=cleaned,
            search_strategy=search_strategy,
            subtopics=subtopics,
            open_questions=open_questions,
            created_at=_utc_now(),
        )

    def _subtopics(self, question: str, keywords: list[str]) -> list[str]:
        parts = [
            part.strip(" .?!")
            for part in re.split(r"\b(?:and|vs|versus|,|;)\b", question, flags=re.I)
            if part.strip(" .?!")
        ]
        subtopics = parts[:4]
        for keyword in keywords:
            label = keyword.replace("-", " ").title()
            if label not in subtopics:
                subtopics.append(label)
            if len(subtopics) >= 5:
                break
        return subtopics or [question]


__all__ = ["ResearchPlanner"]
