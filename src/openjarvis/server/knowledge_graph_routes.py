"""FastAPI routes for the local Knowledge Graph."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

knowledge_graph_router = APIRouter(
    prefix="/v1/knowledge-graph",
    tags=["knowledge-graph"],
)


class CreateNodeBody(BaseModel):
    node_type: str
    title: str
    text: str = ""
    ref_id: Optional[str] = None
    ref_table: Optional[str] = None
    source: str = ""
    metadata: dict[str, Any] = {}
    pinned_root: bool = False


class UpdateNodeBody(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    pinned_root: Optional[bool] = None


class CreateEdgeBody(BaseModel):
    source_id: str
    target_id: str
    relationship: str
    weight: float = 1.0
    directed: bool = True
    metadata: dict[str, Any] = {}


class NoteLinkBody(BaseModel):
    source_note_id: str
    target_note_id: str
    relationship: str = "references"
    weight: float = 1.0
    metadata: dict[str, Any] = {}


class MemoryNoteLinkBody(BaseModel):
    memory_id: str
    note_id: str
    relationship: str = "related_to"
    weight: float = 1.0
    metadata: dict[str, Any] = {}


class ResearchSourceBody(BaseModel):
    research_id: str
    source: dict[str, Any]
    title: Optional[str] = None
    summary: str = ""
    metadata: dict[str, Any] = {}


class ProjectDecisionBody(BaseModel):
    project_id: str
    title: str
    decision: str
    rationale: str = ""
    status: str = "accepted"
    made_at: Optional[str] = None
    note_id: Optional[str] = None
    metadata: dict[str, Any] = {}


class TimelineEventBody(BaseModel):
    node_id: Optional[str] = None
    project_id: Optional[str] = None
    event_type: str = "event"
    title: str
    summary: str = ""
    occurred_at: Optional[str] = None
    metadata: dict[str, Any] = {}


def _get_vault_for_graph(request: Request):
    svc = getattr(request.app.state, "knowledge_vault_service", None)
    if svc is None:
        try:
            from openjarvis.knowledge_vault import KnowledgeVaultService

            svc = KnowledgeVaultService()
            request.app.state.knowledge_vault_service = svc
        except Exception as exc:
            logger.debug("Knowledge Vault unavailable for graph: %s", exc)
            return None
    return svc


def _get_memory_for_graph(request: Request):
    svc = getattr(request.app.state, "structured_memory_service", None)
    if svc is None:
        try:
            from openjarvis.memory import MemoryService

            config = getattr(request.app.state, "config", None)
            db_path = None
            if config is not None:
                db_path = getattr(getattr(config, "memory", None), "db_path", None)
            svc = MemoryService(db_path=db_path)
            request.app.state.structured_memory_service = svc
        except Exception as exc:
            logger.debug("Memory unavailable for graph: %s", exc)
            return None
    return svc


def _get_graph(request: Request):
    svc = getattr(request.app.state, "knowledge_graph_service", None)
    if svc is None:
        try:
            from openjarvis.knowledge_graph import KnowledgeGraphService

            svc = KnowledgeGraphService(
                vault_service=_get_vault_for_graph(request),
                memory_service=_get_memory_for_graph(request),
            )
            request.app.state.knowledge_graph_service = svc
        except Exception as exc:
            logger.warning("Failed to initialise KnowledgeGraphService: %s", exc)
            raise HTTPException(
                status_code=503, detail="Knowledge Graph service unavailable"
            ) from exc
    return svc


@knowledge_graph_router.get("/status")
async def graph_status(request: Request):
    return _get_graph(request).status()


@knowledge_graph_router.get("/nodes")
async def list_nodes(
    request: Request,
    node_type: Optional[str] = None,
    pinned_root: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
):
    svc = _get_graph(request)
    return {
        "nodes": svc.list_nodes(
            node_type=node_type,
            pinned_root=pinned_root,
            limit=limit,
            offset=offset,
        )
    }


@knowledge_graph_router.post("/nodes")
async def create_node(body: CreateNodeBody, request: Request):
    try:
        return {"node": _get_graph(request).create_node(**body.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@knowledge_graph_router.get("/nodes/{node_id}")
async def get_node(node_id: str, request: Request):
    try:
        return {"node": _get_graph(request).get_node(node_id)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Graph node not found")


@knowledge_graph_router.patch("/nodes/{node_id}")
async def update_node(node_id: str, body: UpdateNodeBody, request: Request):
    try:
        return {
            "node": _get_graph(request).update_node(
                node_id,
                **body.model_dump(exclude_unset=True),
            )
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Graph node not found")


@knowledge_graph_router.delete("/nodes/{node_id}")
async def delete_node(node_id: str, request: Request):
    deleted = _get_graph(request).delete_node(node_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Graph node not found")
    return {"status": "deleted", "id": node_id}


@knowledge_graph_router.post("/nodes/{node_id}/pin")
async def pin_node(node_id: str, body: dict[str, bool], request: Request):
    try:
        return {
            "node": _get_graph(request).pin_root(
                node_id,
                bool(body.get("pinned", True)),
            )
        }
    except KeyError:
        raise HTTPException(status_code=404, detail="Graph node not found")


@knowledge_graph_router.get("/roots")
async def root_nodes(request: Request, limit: int = 25):
    return {"roots": _get_graph(request).root_nodes(limit=limit)}


@knowledge_graph_router.post("/edges")
async def create_edge(body: CreateEdgeBody, request: Request):
    try:
        return {"edge": _get_graph(request).create_edge(**body.model_dump())}
    except KeyError:
        raise HTTPException(status_code=404, detail="Source or target node not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@knowledge_graph_router.get("/edges")
async def list_edges(
    request: Request,
    node_id: Optional[str] = None,
    relationship: Optional[str] = None,
    direction: str = "both",
    limit: int = 100,
):
    return {
        "edges": _get_graph(request).list_edges(
            node_id=node_id,
            relationship=relationship,
            direction=direction,
            limit=limit,
        )
    }


@knowledge_graph_router.get("/nodes/{node_id}/traverse")
async def traverse(
    node_id: str,
    request: Request,
    max_depth: int = 2,
    relationship: Optional[str] = None,
):
    try:
        return _get_graph(request).traverse(
            node_id,
            max_depth=max_depth,
            relationship=relationship,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Graph node not found")


@knowledge_graph_router.get("/neighborhood")
async def neighborhood_search(
    request: Request,
    q: str = "",
    start_node_id: Optional[str] = None,
    limit: int = 10,
    max_depth: int = 2,
):
    return {
        "results": _get_graph(request).neighborhood_search(
            q,
            start_node_id=start_node_id,
            limit=limit,
            max_depth=max_depth,
        )
    }


@knowledge_graph_router.post("/relationships/note-note")
async def link_notes(body: NoteLinkBody, request: Request):
    try:
        return {"edge": _get_graph(request).link_notes(**body.model_dump())}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@knowledge_graph_router.post("/relationships/memory-note")
async def link_memory_note(body: MemoryNoteLinkBody, request: Request):
    try:
        return {"edge": _get_graph(request).link_memory_to_note(**body.model_dump())}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@knowledge_graph_router.post("/relationships/research-source")
async def link_research_source(body: ResearchSourceBody, request: Request):
    return {
        "edge": _get_graph(request).link_research_to_source(**body.model_dump())
    }


@knowledge_graph_router.post("/decisions")
async def record_decision(body: ProjectDecisionBody, request: Request):
    try:
        return {
            "decision": _get_graph(request).record_project_decision(
                **body.model_dump()
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@knowledge_graph_router.get("/decisions")
async def list_decisions(
    request: Request,
    project_id: Optional[str] = None,
    note_id: Optional[str] = None,
    limit: int = 50,
):
    return {
        "decisions": _get_graph(request).list_project_decisions(
            project_id=project_id,
            note_id=note_id,
            limit=limit,
        )
    }


@knowledge_graph_router.post("/timeline")
async def create_timeline_event(body: TimelineEventBody, request: Request):
    try:
        return {"event": _get_graph(request).add_timeline_event(**body.model_dump())}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@knowledge_graph_router.get("/timeline")
async def list_timeline(
    request: Request,
    node_id: Optional[str] = None,
    project_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
):
    return {
        "events": _get_graph(request).list_timeline(
            node_id=node_id,
            project_id=project_id,
            event_type=event_type,
            limit=limit,
        )
    }


__all__ = ["knowledge_graph_router"]
