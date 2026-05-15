"""Repository semantic indexing API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from openjarvis.repo_index import RepoIndexService

repo_index_router = APIRouter(prefix="/v1/repo", tags=["repo-index"])


class RepoSearchRequest(BaseModel):
    query: str
    cwd: str | None = None
    limit: int = 10


class RepoIndexRequest(BaseModel):
    cwd: str | None = None
    persist_memory: bool = False


def _privacy_mode(request: Request) -> bool:
    registry = getattr(request.app.state, "mode_registry", None)
    if registry is None:
        return False
    try:
        return registry.get_active_mode().mode.id == "privacy"
    except Exception:
        return False


def _structured_memory_service(request: Request) -> Any:
    service = getattr(request.app.state, "structured_memory_service", None)
    if service is not None:
        return service
    try:
        from openjarvis.memory import MemoryService

        config = getattr(request.app.state, "config", None)
        db_path = None
        if config is not None:
            db_path = getattr(getattr(config, "memory", None), "db_path", None)
        service = MemoryService(db_path=db_path)
        request.app.state.structured_memory_service = service
        return service
    except Exception:
        return None


def _service(request: Request) -> RepoIndexService:
    service = getattr(request.app.state, "repo_index_service", None)
    if service is None:
        service = RepoIndexService(memory_service=_structured_memory_service(request))
        request.app.state.repo_index_service = service
    return service


@repo_index_router.get("/summary")
async def repo_summary(
    request: Request,
    cwd: str | None = Query(default=None),
):
    """Return a local-only repository summary."""
    summary = _service(request).repo_summary(cwd, privacy_mode=_privacy_mode(request))
    return summary.to_dict()


@repo_index_router.post("/index")
async def index_repo(body: RepoIndexRequest, request: Request):
    """Explicitly build a repo index, optionally recording metadata in memory."""
    privacy = _privacy_mode(request)
    summary = _service(request).index_repository(
        body.cwd,
        privacy_mode=privacy,
        persist_memory=body.persist_memory and not privacy,
    )
    return summary.to_dict()


@repo_index_router.get("/architecture")
async def architecture_map(
    request: Request,
    cwd: str | None = Query(default=None),
):
    """Return packages, modules, entry points, config, and build files."""
    architecture = _service(request).architecture_map(
        cwd,
        privacy_mode=_privacy_mode(request),
    )
    return architecture.to_dict()


@repo_index_router.post("/search")
async def semantic_search(body: RepoSearchRequest, request: Request):
    """Search indexed repo summaries using local deterministic embeddings."""
    results = _service(request).semantic_search(
        body.query,
        body.cwd,
        limit=body.limit,
        privacy_mode=_privacy_mode(request),
    )
    return {
        "results": [result.to_dict() for result in results],
        "local_only": True,
        "passive_only": True,
        "privacy_mode": _privacy_mode(request),
    }


@repo_index_router.get("/dependency-graph")
async def dependency_graph(
    request: Request,
    cwd: str | None = Query(default=None),
):
    """Return manifest dependency hints and internal import edges."""
    graph = _service(request).dependency_graph(cwd, privacy_mode=_privacy_mode(request))
    return graph.to_dict()


@repo_index_router.get("/stack")
async def detected_stack(
    request: Request,
    cwd: str | None = Query(default=None),
):
    """Return detected language/framework/build/package-manager stack."""
    stack = _service(request).detected_stack(cwd, privacy_mode=_privacy_mode(request))
    return stack.to_dict()


__all__ = ["repo_index_router"]
