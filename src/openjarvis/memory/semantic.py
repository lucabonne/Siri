"""Optional local ChromaDB semantic index for structured memories."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Iterable


class HashEmbeddingFunction:
    """Tiny deterministic embedding function used when ChromaDB is installed.

    This keeps Phase 1 local-only and avoids downloading model weights during
    startup. It is intentionally simple; higher-quality embedding providers can
    replace it later without changing the memory service contract.
    """

    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    def __call__(self, input: Iterable[str]) -> list[list[float]]:  # noqa: A002
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dim
        tokens = text.lower().split()
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:2], "big") % self._dim
            vector[idx] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class ChromaSemanticIndex:
    """Best-effort local semantic index backed by ChromaDB."""

    def __init__(self, path: str | Path, collection_name: str = "memories") -> None:
        self._available = False
        self._error = ""
        self._collection: Any = None
        try:
            import chromadb

            Path(path).mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(path))
            self._collection = client.get_or_create_collection(
                name=collection_name,
                embedding_function=HashEmbeddingFunction(),
                metadata={"hnsw:space": "cosine"},
            )
            self._available = True
        except Exception as exc:
            self._error = str(exc)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def error(self) -> str:
        return self._error

    def upsert(self, memory_id: str, content: str, metadata: dict[str, Any]) -> None:
        if not self._available or self._collection is None:
            return
        try:
            safe_metadata = {
                key: value
                for key, value in metadata.items()
                if isinstance(value, str | int | float | bool)
            }
            self._collection.upsert(
                ids=[memory_id],
                documents=[content],
                metadatas=[safe_metadata],
            )
        except Exception as exc:
            self._available = False
            self._error = str(exc)

    def query(self, query: str, limit: int) -> list[dict[str, Any]]:
        if not self._available or self._collection is None or not query.strip():
            return []
        try:
            result = self._collection.query(query_texts=[query], n_results=limit)
            ids = result.get("ids", [[]])[0]
            distances = result.get("distances", [[]])[0]
            items = []
            for memory_id, distance in zip(ids, distances):
                score = 1.0 / (1.0 + float(distance))
                items.append({"id": memory_id, "score": score})
            return items
        except Exception as exc:
            self._available = False
            self._error = str(exc)
            return []

    def delete(self, memory_id: str) -> None:
        if not self._available or self._collection is None:
            return
        try:
            self._collection.delete(ids=[memory_id])
        except Exception as exc:
            self._available = False
            self._error = str(exc)

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self._available,
            "backend": "chromadb" if self._available else "disabled",
            "error": self._error,
        }


__all__ = ["ChromaSemanticIndex", "HashEmbeddingFunction"]
