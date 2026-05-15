"""Public service API for repository semantic indexing."""

from __future__ import annotations

import os
from typing import Any

from openjarvis.repo_index.architecture import build_architecture_map
from openjarvis.repo_index.build_detection import detect_stack
from openjarvis.repo_index.dependency_graph import build_dependency_graph
from openjarvis.repo_index.language_detection import detect_languages
from openjarvis.repo_index.models import (
    ArchitectureMap,
    DependencyGraph,
    DetectedStack,
    RepoSummary,
    SemanticSearchResult,
)
from openjarvis.repo_index.scanner import RepoScanner
from openjarvis.repo_index.semantic_index import RepoSemanticIndex, summarize_files


class RepoIndexService:
    """Passive local repository index service.

    The service never executes project code, never modifies repositories, and
    never uploads content. All embeddings are deterministic local hash vectors.
    """

    def __init__(
        self,
        *,
        max_files: int = 1200,
        max_file_bytes: int = 250_000,
        memory_service: Any | None = None,
    ) -> None:
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self.memory_service = memory_service
        self._cache: dict[str, tuple[RepoSummary, RepoSemanticIndex]] = {}

    def index_repository(
        self,
        cwd: str | os.PathLike[str] | None = None,
        *,
        privacy_mode: bool = False,
        persist_memory: bool = False,
    ) -> RepoSummary:
        scanner = RepoScanner(
            cwd,
            max_files=self.max_files,
            max_file_bytes=self.max_file_bytes,
        )
        files, skipped = scanner.scan()
        language_counts = detect_languages(files)
        git_root = RepoScanner.git_root(scanner.root)
        git_repository = str(git_root or "")
        current_branch = RepoScanner.current_branch(scanner.root) if git_root else ""
        stack = detect_stack(
            scanner.root,
            files,
            git_repository=git_repository,
            current_branch=current_branch,
            language_counts=language_counts,
        )
        graph = build_dependency_graph(
            scanner.root,
            files,
            package_managers=stack.package_managers,
        )
        architecture = build_architecture_map(
            scanner.root,
            files,
            stack=stack.to_dict(),
            dependency_graph=graph,
        )
        file_summaries = summarize_files(scanner.root, files)
        summary = RepoSummary(
            root=str(scanner.root),
            git_repository=git_repository,
            current_branch=current_branch,
            file_count=len(files),
            indexed_file_count=len(file_summaries),
            languages=dict(language_counts),
            detected_stack=stack,
            architecture=architecture,
            dependency_graph=graph,
            file_summaries=file_summaries,
            skipped_paths=skipped,
            privacy_mode=privacy_mode,
        )
        self._cache[str(scanner.root)] = (summary, RepoSemanticIndex(file_summaries))
        if persist_memory and not privacy_mode:
            self._record_memory(summary)
        return summary

    def repo_summary(
        self,
        cwd: str | os.PathLike[str] | None = None,
        *,
        privacy_mode: bool = False,
    ) -> RepoSummary:
        return self.index_repository(cwd, privacy_mode=privacy_mode)

    def architecture_map(
        self,
        cwd: str | os.PathLike[str] | None = None,
        *,
        privacy_mode: bool = False,
    ) -> ArchitectureMap:
        return self.repo_summary(cwd, privacy_mode=privacy_mode).architecture

    def dependency_graph(
        self,
        cwd: str | os.PathLike[str] | None = None,
        *,
        privacy_mode: bool = False,
    ) -> DependencyGraph:
        return self.repo_summary(cwd, privacy_mode=privacy_mode).dependency_graph

    def detected_stack(
        self,
        cwd: str | os.PathLike[str] | None = None,
        *,
        privacy_mode: bool = False,
    ) -> DetectedStack:
        return self.repo_summary(cwd, privacy_mode=privacy_mode).detected_stack

    def semantic_search(
        self,
        query: str,
        cwd: str | os.PathLike[str] | None = None,
        *,
        limit: int = 10,
        privacy_mode: bool = False,
    ) -> list[SemanticSearchResult]:
        summary = self.repo_summary(cwd, privacy_mode=privacy_mode)
        index = self._cache.get(summary.root, (summary, RepoSemanticIndex()))[1]
        return index.search(query, limit=limit)

    def _record_memory(self, summary: RepoSummary) -> None:
        if self.memory_service is None:
            return
        try:
            self.memory_service.record_repo_index_summary(summary.to_dict())
        except Exception:
            return


def get_repo_index_service(memory_service: Any | None = None) -> RepoIndexService:
    return RepoIndexService(memory_service=memory_service)


__all__ = ["RepoIndexService", "get_repo_index_service"]
