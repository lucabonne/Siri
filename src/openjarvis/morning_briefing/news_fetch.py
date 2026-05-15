"""Small RSS/Atom news fetcher for morning briefings.

This module intentionally stays dependency-light and source-aware. Privacy Mode
is enforced by the service before this fetcher is called.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Iterable

import httpx

from openjarvis.morning_briefing.models import NewsItem

DEFAULT_FEEDS: tuple[dict[str, str], ...] = (
    {"name": "BBC World", "url": "https://feeds.bbci.co.uk/news/world/rss.xml"},
    {"name": "NPR World", "url": "https://feeds.npr.org/1004/rss.xml"},
    {"name": "Hacker News", "url": "https://hnrss.org/frontpage"},
)


def _clean_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_date(value: str) -> str:
    if not value:
        return ""
    try:
        dt = parsedate_to_datetime(value)
        return dt.isoformat()
    except (TypeError, ValueError):
        return value.strip()


def parse_feed(
    xml_text: str,
    *,
    source_name: str = "",
    max_items: int = 10,
) -> list[NewsItem]:
    """Parse RSS or Atom XML into source-backed news items."""

    root = ET.fromstring(xml_text)
    items: list[NewsItem] = []

    for item_el in root.iter("item"):
        if len(items) >= max_items:
            break
        title = _clean_text(item_el.findtext("title") or "")
        if not title:
            continue
        items.append(
            NewsItem(
                title=title,
                summary=_clean_text(item_el.findtext("description") or ""),
                source_url=_clean_text(item_el.findtext("link") or ""),
                source_name=source_name,
                published_at=_normalize_date(item_el.findtext("pubDate") or ""),
            )
        )

    if items:
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry_el in root.iter("{http://www.w3.org/2005/Atom}entry"):
        if len(items) >= max_items:
            break
        title = _clean_text(entry_el.findtext("atom:title", namespaces=ns) or "")
        if not title:
            continue
        link_el = entry_el.find("atom:link", ns)
        items.append(
            NewsItem(
                title=title,
                summary=_clean_text(
                    entry_el.findtext("atom:summary", namespaces=ns)
                    or entry_el.findtext("atom:content", namespaces=ns)
                    or ""
                ),
                source_url=(
                    link_el.get("href", "").strip() if link_el is not None else ""
                ),
                source_name=source_name,
                published_at=_normalize_date(
                    entry_el.findtext("atom:updated", namespaces=ns)
                    or entry_el.findtext("atom:published", namespaces=ns)
                    or ""
                ),
            )
        )

    return items


class NewsFetcher:
    """Fetch recent news from configured RSS/Atom feeds."""

    def __init__(
        self,
        feeds: Iterable[dict[str, str]] | None = None,
        *,
        timeout_seconds: float = 12.0,
    ) -> None:
        self.feeds = list(feeds or DEFAULT_FEEDS)
        self.timeout_seconds = timeout_seconds

    def fetch(self, *, max_items: int = 12) -> list[NewsItem]:
        if max_items <= 0:
            return []

        per_feed = max(1, max_items // max(1, len(self.feeds)) + 1)
        collected: list[NewsItem] = []
        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=True,
        ) as client:
            for feed in self.feeds:
                if len(collected) >= max_items:
                    break
                url = str(feed.get("url", "")).strip()
                if not url:
                    continue
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    collected.extend(
                        parse_feed(
                            response.text,
                            source_name=str(feed.get("name", "")),
                            max_items=per_feed,
                        )
                    )
                except (httpx.HTTPError, ET.ParseError):
                    continue

        return collected[:max_items]


__all__ = ["DEFAULT_FEEDS", "NewsFetcher", "parse_feed"]
