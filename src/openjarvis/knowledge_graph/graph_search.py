"""Traversal and local semantic-neighborhood search."""

from __future__ import annotations

import re
import sqlite3
from collections import deque
from typing import Any

from openjarvis.knowledge_graph import edges, nodes, timelines

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]{2,}")


def tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text)}


def traversal(
    conn: sqlite3.Connection,
    start_node_id: str,
    *,
    max_depth: int = 2,
    relationship: str | None = None,
) -> dict[str, Any]:
    center = nodes.get_node(conn, start_node_id)
    seen = {center["id"]}
    found_nodes = {center["id"]: center}
    found_edges: dict[str, dict[str, Any]] = {}
    queue: deque[tuple[str, int]] = deque([(center["id"], 0)])

    while queue:
        node_id, depth = queue.popleft()
        if depth >= max(0, min(max_depth, 5)):
            continue
        for edge in edges.list_edges(
            conn,
            node_id=node_id,
            relationship=relationship,
            direction="both",
            limit=200,
        ):
            found_edges[edge["id"]] = edge
            other_id = (
                edge["target_id"] if edge["source_id"] == node_id else edge["source_id"]
            )
            if other_id in seen:
                continue
            try:
                found_nodes[other_id] = nodes.get_node(conn, other_id)
            except KeyError:
                continue
            seen.add(other_id)
            queue.append((other_id, depth + 1))

    return {
        "center": center,
        "nodes": list(found_nodes.values()),
        "edges": list(found_edges.values()),
        "timeline": timelines.list_events(conn, node_id=start_node_id, limit=50),
        "roots": nodes.list_nodes(conn, pinned_root=True, limit=20),
        "local_only": True,
    }


def semantic_neighborhood_search(
    conn: sqlite3.Connection,
    query: str,
    *,
    start_node_id: str | None = None,
    limit: int = 10,
    max_depth: int = 2,
    fts_enabled: bool = True,
) -> list[dict[str, Any]]:
    query_tokens = tokens(query)
    candidates: dict[str, dict[str, Any]] = {}
    for node in nodes.search_nodes(
        conn, query, limit=max(limit * 3, 25), fts_enabled=fts_enabled
    ):
        candidates[node["id"]] = node
    if start_node_id:
        hood = traversal(conn, start_node_id, max_depth=max_depth)
        for node in hood["nodes"]:
            candidates[node["id"]] = node

    scored: list[dict[str, Any]] = []
    for node in candidates.values():
        haystack = " ".join(
            [
                node.get("title", ""),
                node.get("text", ""),
                node.get("node_type", ""),
                str(node.get("metadata", {})),
            ]
        )
        overlap = query_tokens & tokens(haystack)
        adjacent = edges.list_edges(conn, node_id=node["id"], limit=10)
        score = float(len(overlap))
        reasons = [f"matched: {', '.join(sorted(overlap)[:5])}"] if overlap else []
        if node.get("pinned_root"):
            score += 0.5
            reasons.append("pinned root")
        if start_node_id and node["id"] != start_node_id:
            score += min(1.0, len(adjacent) * 0.1)
            if adjacent:
                reasons.append("connected neighborhood")
        if not reasons and query.strip():
            continue
        scored.append(
            {
                "node": node,
                "score": score or 0.1,
                "reasons": reasons or ["nearby node"],
                "edges": adjacent,
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(1, min(limit, 50))]


__all__ = ["traversal", "semantic_neighborhood_search", "tokens"]
