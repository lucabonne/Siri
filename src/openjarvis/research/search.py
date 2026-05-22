"""Local-first source collection for research sessions."""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any

from openjarvis.research.models import ResearchPlan, ResearchSource


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"research-source-{digest}"


def _score(text: str, plan: ResearchPlan) -> float:
    haystack = text.lower()
    terms = {
        term
        for term in re.findall(
            r"[a-z0-9][a-z0-9_-]{2,}",
            " ".join([plan.question, *plan.subtopics]).lower(),
        )
        if term not in {"and", "the", "for", "with", "from"}
    }
    if not terms:
        return 0.2
    hits = sum(1 for term in terms if term in haystack)
    return min(1.0, hits / max(4, len(terms)) + 0.15)


class SourceSearch:
    """Collect explicit, cached, and optional external sources."""

    def collect(
        self,
        *,
        plan: ResearchPlan,
        memory_service: Any = None,
        worldmonitor_service: Any = None,
        morning_briefing_service: Any = None,
        seed_sources: list[dict[str, Any]] | None = None,
        allow_external_search: bool = False,
        privacy_mode: bool = False,
        max_sources: int = 8,
    ) -> list[ResearchSource]:
        sources: list[ResearchSource] = []
        sources.extend(self._from_seed(seed_sources or [], plan))
        sources.extend(self._from_memory(memory_service, plan, limit=max_sources))
        sources.extend(
            self._from_morning_briefing(
                morning_briefing_service,
                plan,
                limit=max_sources,
            )
        )
        sources.extend(
            self._from_worldmonitor(worldmonitor_service, plan, limit=max_sources)
        )

        if allow_external_search and not privacy_mode:
            sources.extend(self._from_ddgs(plan, limit=max_sources))

        deduped: dict[str, ResearchSource] = {}
        for source in sources:
            key = source.url or source.title or source.id
            current = deduped.get(key)
            if current is None or source.relevance > current.relevance:
                deduped[key] = source

        ranked = sorted(
            deduped.values(),
            key=lambda source: (source.relevance, source.access_date),
            reverse=True,
        )
        return ranked[: max(1, min(max_sources, 25))]

    def _from_seed(
        self,
        seed_sources: list[dict[str, Any]],
        plan: ResearchPlan,
    ) -> list[ResearchSource]:
        sources: list[ResearchSource] = []
        for item in seed_sources:
            title = str(item.get("title") or item.get("url") or "User supplied source")
            url = str(item.get("url") or "")
            snippet = str(item.get("snippet") or item.get("content") or title)
            sources.append(
                ResearchSource(
                    id=str(item.get("id") or _stable_id(title, url)),
                    title=title,
                    url=url,
                    access_date=str(item.get("access_date") or _utc_now()),
                    relevance=float(item.get("relevance") or _score(snippet, plan)),
                    snippet=snippet,
                    source_type="provided",
                    metadata=dict(item.get("metadata") or {}),
                )
            )
        return sources

    def _from_memory(
        self,
        memory_service: Any,
        plan: ResearchPlan,
        *,
        limit: int,
    ) -> list[ResearchSource]:
        if memory_service is None:
            return []
        try:
            memories = memory_service.search_memories(plan.question, limit=limit)
        except Exception:
            return []
        sources: list[ResearchSource] = []
        for memory in memories:
            source = memory.get("source") or {}
            title = str(
                source.get("title")
                or memory.get("content", "")[:80]
                or "Memory"
            )
            url = str(source.get("url") or "")
            snippet = str(memory.get("content") or "")
            sources.append(
                ResearchSource(
                    id=_stable_id(str(memory.get("id", "")), title, url),
                    title=title,
                    url=url,
                    access_date=str(
                        source.get("timestamp")
                        or memory.get("created_at")
                        or _utc_now()
                    ),
                    relevance=max(
                        float(memory.get("score") or 0.0),
                        float(source.get("relevance") or 0.0),
                        _score(snippet, plan),
                    ),
                    snippet=snippet,
                    source_type=f"memory:{memory.get('memory_type', 'note')}",
                    metadata={
                        "memory_id": memory.get("id", ""),
                        "tags": memory.get("tags", []),
                    },
                )
            )
        return sources

    def _from_morning_briefing(
        self,
        morning_briefing_service: Any,
        plan: ResearchPlan,
        *,
        limit: int,
    ) -> list[ResearchSource]:
        if morning_briefing_service is None:
            return []
        try:
            briefing = morning_briefing_service.latest_briefing()
        except Exception:
            return []
        if briefing is None:
            return []
        sources: list[ResearchSource] = []
        for event in briefing.events[:limit]:
            snippet = f"{event.title}. {event.summary}"
            sources.append(
                ResearchSource(
                    id=_stable_id(event.id, event.source_url),
                    title=event.title,
                    url=event.source_url,
                    access_date=event.created_at or briefing.generated_at,
                    relevance=_score(snippet, plan),
                    snippet=snippet,
                    source_type="morning_briefing",
                    metadata={
                        "briefing_id": briefing.id,
                        "event_id": event.id,
                        "category": event.category,
                    },
                )
            )
        return sources

    def _from_worldmonitor(
        self,
        worldmonitor_service: Any,
        plan: ResearchPlan,
        *,
        limit: int,
    ) -> list[ResearchSource]:
        if worldmonitor_service is None:
            return []
        try:
            events = worldmonitor_service.imported_events(limit=limit)
        except Exception:
            return []
        sources: list[ResearchSource] = []
        for event in events:
            snippet = f"{event.title}. {event.summary}"
            sources.append(
                ResearchSource(
                    id=_stable_id(event.id, event.source_url),
                    title=event.title,
                    url=event.source_url,
                    access_date=event.imported_at or event.published_at or _utc_now(),
                    relevance=_score(snippet, plan),
                    snippet=snippet,
                    source_type="worldmonitor",
                    metadata={
                        "worldmonitor_event_id": event.id,
                        "category": event.category,
                        "source_name": event.source_name,
                    },
                )
            )
        return sources

    def _from_ddgs(self, plan: ResearchPlan, *, limit: int) -> list[ResearchSource]:
        try:
            from ddgs import DDGS
        except Exception:
            return []

        sources: list[ResearchSource] = []
        try:
            with DDGS() as ddgs:
                results = ddgs.text(plan.question, max_results=max(1, min(limit, 10)))
        except Exception:
            return []
        for item in results:
            title = str(item.get("title") or item.get("href") or "Search result")
            url = str(item.get("href") or item.get("url") or "")
            snippet = str(item.get("body") or "")
            sources.append(
                ResearchSource(
                    id=_stable_id(title, url),
                    title=title,
                    url=url,
                    access_date=_utc_now(),
                    relevance=_score(f"{title}. {snippet}", plan),
                    snippet=snippet,
                    source_type="external_search",
                    metadata={"provider": "ddgs"},
                )
            )
        return sources


__all__ = ["SourceSearch"]
