"""Local semantic indexing for repository files."""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Iterable

from openjarvis.repo_index.language_detection import is_source_language
from openjarvis.repo_index.models import FileSummary, RepoFile, SemanticSearchResult


class HashEmbedder:
    """Deterministic local embedding helper.

    The Phase 1 index intentionally avoids network calls and model downloads.
    This hash vector is lightweight but still gives useful fuzzy search over
    file summaries and symbol names.
    """

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:2], "big") % self.dim
            vector[idx] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class RepoSemanticIndex:
    """In-memory semantic search index built from safe local file summaries."""

    def __init__(self, summaries: Iterable[FileSummary] = ()) -> None:
        self._embedder = HashEmbedder()
        self._summaries = list(summaries)
        self._vectors = [
            self._embedder.embed(_search_text(summary)) for summary in self._summaries
        ]

    @property
    def summaries(self) -> list[FileSummary]:
        return list(self._summaries)

    def search(self, query: str, *, limit: int = 10) -> list[SemanticSearchResult]:
        if not query.strip():
            return []
        query_vector = self._embedder.embed(query)
        query_tokens = set(_tokens(query))
        scored = []
        for summary, vector in zip(self._summaries, self._vectors):
            semantic = _cosine(query_vector, vector)
            lexical = _lexical_score(query_tokens, _search_text(summary))
            score = semantic * 0.7 + lexical * 0.3
            if score > 0:
                scored.append((score, summary))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            SemanticSearchResult(
                path=summary.path,
                summary=summary.summary,
                score=round(float(score), 4),
                language=summary.language,
                symbols=summary.symbols,
                imports=summary.imports,
            )
            for score, summary in scored[: max(1, min(limit, 50))]
        ]


def summarize_files(root: str | Path, files: Iterable[RepoFile]) -> list[FileSummary]:
    """Create compact summaries for safe repository files."""
    root_path = Path(root)
    summaries: list[FileSummary] = []
    for file in files:
        if not file.language or (
            not is_source_language(file.language)
            and Path(file.path).name
            not in {"package.json", "pyproject.toml", "Cargo.toml"}
        ):
            continue
        text = _read_text(root_path / file.path, max_chars=40_000)
        summaries.append(_summarize_file(file, text))
    return summaries


def _summarize_file(file: RepoFile, text: str) -> FileSummary:
    symbols = _symbols(text, file.language)
    imports = _imports(text, file.language)
    line_count = text.count("\n") + (1 if text else 0)
    headline = _headline(text)
    summary_parts = [
        f"{file.path} is a {file.language or 'text'} file",
        f"{line_count} lines",
    ]
    if symbols:
        summary_parts.append(f"symbols: {', '.join(symbols[:8])}")
    if imports:
        summary_parts.append(f"imports: {', '.join(imports[:8])}")
    if headline:
        summary_parts.append(headline)
    return FileSummary(
        path=file.path,
        language=file.language,
        summary="; ".join(summary_parts),
        symbols=symbols[:40],
        imports=imports[:40],
        size_bytes=file.size_bytes,
    )


def _symbols(text: str, language: str) -> list[str]:
    patterns = []
    if language == "Python":
        patterns = [r"^\s*def\s+([A-Za-z_][\w]*)", r"^\s*class\s+([A-Za-z_][\w]*)"]
    elif language == "Java":
        patterns = [
            r"\bclass\s+([A-Za-z_][\w]*)",
            r"\binterface\s+([A-Za-z_][\w]*)",
            r"\benum\s+([A-Za-z_][\w]*)",
        ]
    elif language == "Rust":
        patterns = [
            r"\bfn\s+([A-Za-z_][\w]*)",
            r"\bstruct\s+([A-Za-z_][\w]*)",
            r"\benum\s+([A-Za-z_][\w]*)",
            r"\btrait\s+([A-Za-z_][\w]*)",
        ]
    elif language in {"JavaScript", "TypeScript", "Vue"}:
        patterns = [
            r"\bfunction\s+([A-Za-z_][\w]*)",
            r"\bclass\s+([A-Za-z_][\w]*)",
            r"\bconst\s+([A-Za-z_][\w]*)\s*=",
            r"\bexport\s+function\s+([A-Za-z_][\w]*)",
        ]
    symbols: list[str] = []
    for pattern in patterns:
        symbols.extend(re.findall(pattern, text, re.M))
    return _dedupe(symbols)


def _imports(text: str, language: str) -> list[str]:
    imports: list[str] = []
    if language == "Python":
        imports.extend(
            re.findall(r"^\s*from\s+([A-Za-z0-9_.]+)\s+import\s+", text, re.M)
        )
        imports.extend(re.findall(r"^\s*import\s+([A-Za-z0-9_.]+)", text, re.M))
    elif language == "Java":
        imports.extend(re.findall(r"^\s*import\s+([A-Za-z0-9_.]+);", text, re.M))
    elif language == "Rust":
        imports.extend(re.findall(r"^\s*use\s+([A-Za-z0-9_:]+)", text, re.M))
    elif language in {"JavaScript", "TypeScript", "Vue"}:
        imports.extend(re.findall(r"""from\s+["']([^"']+)["']""", text))
        imports.extend(re.findall(r"""import\s+["']([^"']+)["']""", text))
    return _dedupe(imports)


def _headline(text: str) -> str:
    for line in text.splitlines()[:30]:
        clean = line.strip().strip("#/* ")
        if clean and not clean.startswith(("import ", "from ", "package ")):
            return clean[:140]
    return ""


def _read_text(path: Path, *, max_chars: int) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]
    except OSError:
        return ""


def _search_text(summary: FileSummary) -> str:
    return " ".join(
        [
            summary.path,
            summary.language,
            summary.summary,
            *summary.symbols,
            *summary.imports,
        ]
    )


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_./:-]+", text.lower())


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _lexical_score(query_tokens: set[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    target = set(_tokens(text))
    return len(query_tokens & target) / len(query_tokens)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


__all__ = ["HashEmbedder", "RepoSemanticIndex", "summarize_files"]
