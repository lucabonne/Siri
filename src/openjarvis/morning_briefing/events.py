"""Event categorization and lightweight geocoding for morning briefings."""

from __future__ import annotations

import hashlib
import re

from openjarvis.morning_briefing.models import MorningEvent, NewsItem

CATEGORY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("technology", ("ai", "software", "chip", "cyber", "space", "tech")),
    ("economy", ("market", "bank", "inflation", "trade", "economy", "stock")),
    ("climate", ("climate", "weather", "storm", "flood", "heat", "wildfire")),
    ("security", ("war", "attack", "security", "military", "conflict", "missile")),
    ("health", ("health", "hospital", "vaccine", "disease", "medical")),
    ("politics", ("election", "minister", "president", "parliament", "policy")),
    ("culture", ("film", "music", "museum", "sport", "festival", "award")),
)

LOCATION_COORDINATES: dict[str, tuple[float, float]] = {
    "argentina": (-34.6037, -58.3816),
    "australia": (-35.2809, 149.13),
    "berlin": (52.52, 13.405),
    "brazil": (-15.7939, -47.8828),
    "brussels": (50.8503, 4.3517),
    "china": (39.9042, 116.4074),
    "france": (48.8566, 2.3522),
    "germany": (52.52, 13.405),
    "india": (28.6139, 77.209),
    "israel": (31.7683, 35.2137),
    "italy": (41.9028, 12.4964),
    "japan": (35.6762, 139.6503),
    "london": (51.5072, -0.1276),
    "mexico": (19.4326, -99.1332),
    "new york": (40.7128, -74.006),
    "paris": (48.8566, 2.3522),
    "rome": (41.9028, 12.4964),
    "russia": (55.7558, 37.6173),
    "tokyo": (35.6762, 139.6503),
    "ukraine": (50.4501, 30.5234),
    "united kingdom": (51.5072, -0.1276),
    "united states": (38.9072, -77.0369),
    "washington": (38.9072, -77.0369),
}


def categorize_item(item: NewsItem) -> str:
    text = f"{item.title} {item.summary}".lower()
    for category, keywords in CATEGORY_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return category
    return "world"


def infer_location(
    item: NewsItem,
    *,
    user_location: str = "",
) -> tuple[str, float | None, float | None]:
    text = f"{item.location_name} {item.title} {item.summary} {user_location}".lower()
    for name, (lat, lon) in LOCATION_COORDINATES.items():
        if re.search(rf"\b{re.escape(name)}\b", text):
            return name.title(), lat, lon
    return item.location_name, None, None


def _stable_event_id(item: NewsItem) -> str:
    key = "|".join([item.title, item.source_url, item.published_at])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def categorize_events(
    items: list[NewsItem],
    *,
    user_location: str = "",
) -> list[MorningEvent]:
    """Convert fetched news items into categorized morning events."""

    events: list[MorningEvent] = []
    for item in items:
        location_name, latitude, longitude = infer_location(
            item,
            user_location=user_location,
        )
        summary = item.summary or item.title
        if len(summary) > 240:
            summary = summary[:237].rstrip() + "..."
        events.append(
            MorningEvent(
                id=_stable_event_id(item),
                title=item.title,
                category=categorize_item(item),
                summary=summary,
                source_url=item.source_url,
                source_name=item.source_name,
                published_at=item.published_at,
                latitude=latitude,
                longitude=longitude,
                location_name=location_name,
                importance=3 if item.source_url else 2,
                metadata=item.metadata,
            )
        )
    return events


__all__ = [
    "LOCATION_COORDINATES",
    "categorize_events",
    "categorize_item",
    "infer_location",
]
