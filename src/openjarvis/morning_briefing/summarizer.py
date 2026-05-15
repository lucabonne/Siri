"""Deterministic briefing summarizer used for Phase 1."""

from __future__ import annotations

from collections import Counter

from openjarvis.morning_briefing.models import MorningEvent


class BriefingSummarizer:
    """Create concise local summaries without requiring an LLM call."""

    def summarize(
        self,
        events: list[MorningEvent],
        *,
        location_name: str = "",
    ) -> tuple[str, str]:
        if not events:
            summary = "No fresh external headlines are available yet."
            content = (
                "Daily Briefing\n\n"
                "- No world news items were fetched for this briefing.\n"
                "- Cached briefings remain available in Privacy Mode."
            )
            return summary, content

        categories = Counter(event.category for event in events)
        leading = ", ".join(category for category, _ in categories.most_common(3))
        place = f" for {location_name}" if location_name else ""
        summary = f"{len(events)} source-backed updates{place}, led by {leading}."
        lines = ["Daily Briefing", "", "Top updates:"]
        for event in events[:6]:
            source = f" ({event.source_name})" if event.source_name else ""
            lines.append(f"- [{event.category}] {event.title}{source}: {event.summary}")
        if len(events) > 6:
            remaining = len(events) - 6
            lines.append(
                f"- {remaining} additional events are available on the world map."
            )
        return summary, "\n".join(lines)


__all__ = ["BriefingSummarizer"]
