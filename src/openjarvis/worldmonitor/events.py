"""Normalization helpers for WorldMonitor event payloads."""

from __future__ import annotations

import hashlib
import re
from typing import Any

EVENT_CONTAINER_KEYS = (
    "events",
    "items",
    "articles",
    "news",
    "headlines",
    "features",
    "data",
    "results",
    "clusters",
    "signals",
)

CATEGORY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("security", ("conflict", "military", "war", "attack", "ucdp", "iran")),
    ("climate", ("climate", "earthquake", "eonet", "flood", "fire", "storm")),
    ("economy", ("market", "macro", "commodity", "finance", "stock")),
    ("cyber", ("cyber", "cve", "outage", "infrastructure")),
    ("aviation", ("aviation", "flight", "airport", "aircraft")),
    ("maritime", ("maritime", "vessel", "ship", "ais")),
    ("health", ("health", "disease", "medical")),
    ("technology", ("technology", "ai", "chips", "startup")),
)


def stable_id(value: dict[str, Any], *, namespace: str = "worldmonitor") -> str:
    key = "|".join(
        str(value.get(name) or "")
        for name in (
            "id",
            "eventId",
            "title",
            "headline",
            "url",
            "sourceUrl",
            "publishedAt",
            "timestamp",
        )
    )
    return f"{namespace}-{hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]}"


def text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    return ""


def float_value(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def first_text(data: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = text_value(data.get(name))
        if value:
            return value
    return ""


def infer_category(data: dict[str, Any], *, domain: str = "") -> str:
    explicit = first_text(data, ("category", "type", "kind", "domain", "layer"))
    text = " ".join(
        [
            domain,
            explicit,
            first_text(data, ("title", "headline", "name")),
            first_text(data, ("summary", "description", "signal")),
        ]
    ).lower()
    for category, keywords in CATEGORY_HINTS:
        if any(re.search(rf"\b{re.escape(keyword)}\b", text) for keyword in keywords):
            return category
    return explicit.lower().replace(" ", "-") if explicit else "world"


def find_coordinates(data: dict[str, Any]) -> tuple[float | None, float | None]:
    lat = first_text(data, ("lat", "latitude", "y"))
    lon = first_text(data, ("lon", "lng", "longitude", "x"))
    if not lat and isinstance(data.get("coordinates"), list):
        coords = data["coordinates"]
        if len(coords) >= 2:
            lon = text_value(coords[0])
            lat = text_value(coords[1])
    if not lat and isinstance(data.get("geometry"), dict):
        coordinates = data["geometry"].get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            lon = text_value(coordinates[0])
            lat = text_value(coordinates[1])
    if not lat and isinstance(data.get("location"), dict):
        location = data["location"]
        lat = first_text(location, ("lat", "latitude"))
        lon = first_text(location, ("lon", "lng", "longitude"))
    return float_value(lat), float_value(lon)


def iter_event_dicts(
    payload: Any,
    *,
    domain: str = "",
) -> list[tuple[dict[str, Any], str]]:
    """Extract plausible event/article dictionaries from nested API payloads."""

    found: list[tuple[dict[str, Any], str]] = []

    def visit(value: Any, current_domain: str) -> None:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    title = first_text(item, ("title", "headline", "name", "summary"))
                    if title:
                        found.append((item, current_domain))
                    else:
                        visit(item, current_domain)
            return
        if not isinstance(value, dict):
            return
        for key, nested in value.items():
            next_domain = current_domain or str(key)
            if key in EVENT_CONTAINER_KEYS:
                visit(nested, next_domain)
            elif isinstance(nested, (dict, list)):
                visit(nested, next_domain)

    visit(payload, domain)
    return found


__all__ = [
    "find_coordinates",
    "first_text",
    "infer_category",
    "iter_event_dicts",
    "stable_id",
    "text_value",
]
