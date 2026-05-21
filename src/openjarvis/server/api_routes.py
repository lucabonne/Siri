"""Extended API routes for agents, workflows, memory, traces, etc."""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from openjarvis.server.agent_workspace_routes import agent_workspace_router
from openjarvis.server.coding_assistant_routes import coding_assistant_router
from openjarvis.server.context_routes import context_router
from openjarvis.server.desktop_routes import desktop_router
from openjarvis.server.engineering_routes import engineering_router
from openjarvis.server.mode_routes import mode_router
from openjarvis.server.morning_briefing_routes import morning_briefing_router
from openjarvis.server.notification_routes import notification_router
from openjarvis.server.packaging_routes import packaging_router
from openjarvis.server.repo_index_routes import repo_index_router
from openjarvis.server.research_routes import research_router
from openjarvis.server.startup_routes import startup_router
from openjarvis.server.workflow_routes import workflow_router
from openjarvis.server.worldmonitor_routes import worldmonitor_router

logger = logging.getLogger(__name__)

# ---- Request/Response models ----


class AgentCreateRequest(BaseModel):
    agent_type: str
    tools: Optional[List[str]] = None
    agent_id: Optional[str] = None


class AgentMessageRequest(BaseModel):
    message: str


class MemoryStoreRequest(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None
    memory_type: str = "note"
    project_id: Optional[str] = None
    source: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    pinned: bool = False


class MemorySearchRequest(BaseModel):
    query: str
    top_k: int = 5
    project_id: Optional[str] = None
    memory_type: Optional[str] = None
    created_after: Optional[str] = None
    created_before: Optional[str] = None
    pinned: Optional[bool] = None


class MemoryPinRequest(BaseModel):
    pinned: bool


class MemoryIndexRequest(BaseModel):
    path: str


class BudgetLimitsRequest(BaseModel):
    max_tokens_per_day: Optional[int] = None
    max_requests_per_hour: Optional[int] = None


class FeedbackScoreRequest(BaseModel):
    trace_id: str
    score: float
    source: str = "api"


class OptimizeRunRequest(BaseModel):
    benchmark: str
    max_trials: int = 20
    optimizer_model: str = "claude-sonnet-4-6"
    max_samples: int = 50


class VoiceStartRecordingRequest(BaseModel):
    agent_id: str = ""
    approved: bool = False
    persist_raw_audio: Optional[bool] = None


class VoiceTranscribeLatestRequest(BaseModel):
    language: str = ""


class HotkeyEnableRequest(BaseModel):
    approved: bool = True
    binding: str = ""
    fallback: str = ""


class HotkeyTestTriggerRequest(BaseModel):
    approved: bool = True


class TTSSpeakApiRequest(BaseModel):
    text: str
    voice_id: str = ""
    engine: str = ""
    user_triggered: bool = True
    allow_quiet: bool = False
    speed: float = 1.0


# ---- Agent routes ----

agents_router = APIRouter(prefix="/v1/agents", tags=["agents"])


@agents_router.get("")
async def list_agents(request: Request):
    """List available agent types and running agents."""
    registered = []
    try:
        import openjarvis.agents  # noqa: F401 — side-effect registration
        from openjarvis.core.registry import AgentRegistry

        for key in sorted(AgentRegistry.keys()):
            cls = AgentRegistry.get(key)
            registered.append(
                {
                    "key": key,
                    "class": cls.__name__,
                    "accepts_tools": getattr(cls, "accepts_tools", False),
                }
            )
    except Exception as exc:
        logger.warning("Failed to list registered agents: %s", exc)

    running = []
    try:
        from openjarvis.tools.agent_tools import _SPAWNED_AGENTS

        running = [{"id": k, **v} for k, v in _SPAWNED_AGENTS.items()]
    except ImportError:
        pass

    return {"registered": registered, "running": running}


@agents_router.post("")
async def create_agent(req: AgentCreateRequest, request: Request):
    """Spawn a new agent."""
    try:
        from openjarvis.tools.agent_tools import AgentSpawnTool

        tool = AgentSpawnTool()
        params = {"agent_type": req.agent_type}
        if req.tools:
            params["tools"] = ",".join(req.tools)
        if req.agent_id:
            params["agent_id"] = req.agent_id
        result = tool.execute(**params)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.content)
        return {
            "status": "created",
            "content": result.content,
            "metadata": result.metadata,
        }
    except ImportError:
        raise HTTPException(status_code=501, detail="Agent tools not available")


@agents_router.delete("/{agent_id}")
async def kill_agent(agent_id: str, request: Request):
    """Kill a running agent."""
    try:
        from openjarvis.tools.agent_tools import AgentKillTool

        tool = AgentKillTool()
        result = tool.execute(agent_id=agent_id)
        if not result.success:
            raise HTTPException(status_code=404, detail=result.content)
        return {"status": "stopped", "agent_id": agent_id}
    except ImportError:
        raise HTTPException(status_code=501, detail="Agent tools not available")


@agents_router.post("/{agent_id}/message")
async def message_agent(agent_id: str, req: AgentMessageRequest, request: Request):
    """Send a message to a running agent."""
    try:
        from openjarvis.tools.agent_tools import AgentSendTool

        tool = AgentSendTool()
        result = tool.execute(agent_id=agent_id, message=req.message)
        if not result.success:
            raise HTTPException(status_code=404, detail=result.content)
        return {"status": "sent", "content": result.content}
    except ImportError:
        raise HTTPException(status_code=501, detail="Agent tools not available")


# ---- Memory routes ----

memory_router = APIRouter(prefix="/v1/memory", tags=["memory"])


def _get_structured_memory_service(request: Request):
    """Return the app-level structured memory service, creating one lazily."""
    service = getattr(request.app.state, "structured_memory_service", None)
    if service is None:
        try:
            from openjarvis.memory import MemoryService

            config = getattr(request.app.state, "config", None)
            db_path = None
            if config is not None:
                db_path = getattr(getattr(config, "memory", None), "db_path", None)
            service = MemoryService(db_path=db_path)
            request.app.state.structured_memory_service = service
        except Exception as exc:
            logger.warning("Failed to initialize structured memory service: %s", exc)
            return None
    return service


def _get_memory_backend(request: Request):
    """Return the app-level memory backend, falling back to a fresh SQLiteMemory."""
    backend = getattr(request.app.state, "memory_backend", None)
    if backend is None:
        try:
            from openjarvis.tools.storage.sqlite import SQLiteMemory

            backend = SQLiteMemory()
        except Exception:
            return None
    return backend


@memory_router.post("/store")
async def memory_store(req: MemoryStoreRequest, request: Request):
    """Store content in memory."""
    service = _get_structured_memory_service(request)
    if service is not None:
        try:
            memory = service.create_memory(
                req.content,
                memory_type=req.memory_type,
                project_id=req.project_id,
                source=req.source,
                metadata=req.metadata or {},
                tags=req.tags or [],
                pinned=req.pinned,
            )
            return {"status": "stored", "id": memory["id"], "memory": memory}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    backend = _get_memory_backend(request)
    if backend is None:
        return {"status": "stored", "note": "no backend available"}
    try:
        backend.store(req.content, metadata=req.metadata or {})
        return {"status": "stored"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@memory_router.post("/search")
async def memory_search(req: MemorySearchRequest, request: Request):
    """Search memory for relevant content."""
    service = _get_structured_memory_service(request)
    if service is not None:
        try:
            results = service.search_memories(
                req.query,
                project_id=req.project_id,
                memory_type=req.memory_type,
                created_after=req.created_after,
                created_before=req.created_before,
                pinned=req.pinned,
                limit=req.top_k,
            )
            return {"results": results}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    backend = _get_memory_backend(request)
    if backend is None:
        return {"results": []}
    try:
        results = backend.retrieve(req.query, top_k=req.top_k)
        items = [
            {
                "content": r.content,
                "score": getattr(r, "score", 0.0),
                "metadata": getattr(r, "metadata", {}),
            }
            for r in results
        ]
        return {"results": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@memory_router.get("/stats")
async def memory_stats(request: Request):
    """Get memory backend statistics."""
    service = _get_structured_memory_service(request)
    if service is not None:
        try:
            return {
                "entries": service.count(),
                "backend": "sqlite_structured",
                "semantic": service.semantic_status(),
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    backend = _get_memory_backend(request)
    if backend is None:
        return {"entries": 0, "backend": "none", "status": "not_configured"}
    try:
        return {
            "entries": backend.count(),
            "backend": getattr(backend, "backend_id", "unknown"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@memory_router.get("/config")
async def memory_config(request: Request):
    """Return current memory configuration."""
    try:
        config = getattr(request.app.state, "config", None)
        if config is None:
            from openjarvis.core.config import load_config

            config = load_config()
        backend = getattr(request.app.state, "memory_backend", None)
        return {
            "backend_type": (
                backend.backend_id
                if backend is not None
                else config.memory.default_backend
            ),
            "context_top_k": config.memory.context_top_k,
            "context_min_score": config.memory.context_min_score,
            "context_max_tokens": config.memory.context_max_tokens,
            "context_from_memory": config.agent.context_from_memory,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@memory_router.post("/index")
async def memory_index(req: MemoryIndexRequest, request: Request):
    """Index files from a path into memory."""
    try:
        from pathlib import Path

        from openjarvis.tools.storage.ingest import ingest_path

        target = Path(req.path).expanduser().resolve()
        if not target.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {req.path}")

        backend = _get_memory_backend(request)
        if backend is None:
            raise HTTPException(status_code=503, detail="No memory backend available")

        chunks = ingest_path(target)
        stored = 0
        for chunk in chunks:
            metadata = {"source": getattr(chunk, "source", str(target))}
            if hasattr(chunk, "metadata") and chunk.metadata:
                metadata.update(chunk.metadata)
            backend.store(chunk.content, metadata=metadata)
            stored += 1

        return {"status": "indexed", "chunks_indexed": stored}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@memory_router.get("")
async def memory_list(
    request: Request,
    project_id: Optional[str] = None,
    memory_type: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    pinned: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List structured memories with optional filters."""
    service = _get_structured_memory_service(request)
    if service is None:
        return {"memories": []}
    try:
        return {
            "memories": service.list_memories(
                project_id=project_id,
                memory_type=memory_type,
                created_after=created_after,
                created_before=created_before,
                pinned=pinned,
                limit=limit,
                offset=offset,
            )
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@memory_router.post("")
async def memory_create(req: MemoryStoreRequest, request: Request):
    """Create a structured memory."""
    service = _get_structured_memory_service(request)
    if service is None:
        raise HTTPException(status_code=503, detail="Structured memory unavailable")
    try:
        memory = service.create_memory(
            req.content,
            memory_type=req.memory_type,
            project_id=req.project_id,
            source=req.source,
            metadata=req.metadata or {},
            tags=req.tags or [],
            pinned=req.pinned,
        )
        return {"memory": memory}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@memory_router.delete("/{memory_id}")
async def memory_delete(memory_id: str, request: Request):
    """Delete a structured memory."""
    service = _get_structured_memory_service(request)
    if service is None:
        raise HTTPException(status_code=503, detail="Structured memory unavailable")
    try:
        deleted = service.delete_memory(memory_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"status": "deleted", "id": memory_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@memory_router.post("/{memory_id}/pin")
async def memory_pin(memory_id: str, req: MemoryPinRequest, request: Request):
    """Pin or unpin a structured memory."""
    service = _get_structured_memory_service(request)
    if service is None:
        raise HTTPException(status_code=503, detail="Structured memory unavailable")
    try:
        return {"memory": service.set_pinned(memory_id, req.pinned)}
    except KeyError:
        raise HTTPException(status_code=404, detail="Memory not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---- Traces routes ----

traces_router = APIRouter(prefix="/v1/traces", tags=["traces"])


def _serialise_trace(trace) -> dict:
    """Convert a Trace dataclass to a frontend-friendly dict."""
    import datetime
    from dataclasses import asdict

    d = asdict(trace)
    d["id"] = d.pop("trace_id", "")
    started = d.pop("started_at", 0.0)
    d["created_at"] = (
        datetime.datetime.fromtimestamp(started, tz=datetime.timezone.utc).isoformat()
        if started
        else None
    )
    dur = d.pop("total_latency_seconds", 0.0)
    d["duration_ms"] = round(dur * 1000)
    for step in d.get("steps", []):
        st = step.get("step_type")
        if hasattr(st, "value"):
            step["step_type"] = st.value
    return d


@traces_router.get("")
async def list_traces(request: Request, limit: int = 20):
    """List recent traces."""
    try:
        store = getattr(request.app.state, "trace_store", None)
        if store is None:
            return {"traces": []}
        traces = store.list_traces(limit=limit)
        items = [_serialise_trace(t) for t in traces]
        return {"traces": items}
    except Exception as exc:
        return {"traces": [], "error": str(exc)}


@traces_router.get("/{trace_id}")
async def get_trace(trace_id: str, request: Request):
    """Get a specific trace by ID."""
    try:
        store = getattr(request.app.state, "trace_store", None)
        if store is None:
            raise HTTPException(status_code=404, detail="Trace not found")
        trace = store.get(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="Trace not found")
        return _serialise_trace(trace)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---- Telemetry routes ----

telemetry_router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"])


@telemetry_router.get("/stats")
async def telemetry_stats(request: Request):
    """Get aggregated telemetry statistics."""
    try:
        from dataclasses import asdict

        from openjarvis.core.config import DEFAULT_CONFIG_DIR
        from openjarvis.telemetry.aggregator import TelemetryAggregator

        db_path = DEFAULT_CONFIG_DIR / "telemetry.db"
        if not db_path.exists():
            return {"total_requests": 0, "total_tokens": 0}

        session_start = getattr(request.app.state, "session_start", None)
        agg = TelemetryAggregator(db_path)
        try:
            stats = agg.summary(since=session_start)
            d = asdict(stats)
            d.pop("per_model", None)
            d.pop("per_engine", None)
            d["total_requests"] = d.pop("total_calls", 0)
            return d
        finally:
            agg.close()
    except Exception as exc:
        return {"error": str(exc)}


@telemetry_router.get("/energy")
async def telemetry_energy(request: Request):
    """Get energy monitoring data."""
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR
        from openjarvis.telemetry.aggregator import TelemetryAggregator

        db_path = DEFAULT_CONFIG_DIR / "telemetry.db"
        if not db_path.exists():
            return {
                "total_energy_j": 0,
                "energy_per_token_j": 0,
                "avg_power_w": 0,
                "cpu_temp_c": None,
                "gpu_temp_c": None,
            }

        session_start = getattr(request.app.state, "session_start", None)
        agg = TelemetryAggregator(db_path)
        try:
            stats = agg.summary(since=session_start)
            total_energy = stats.total_energy_joules
            total_tokens = stats.total_tokens
            total_latency = stats.total_latency
            return {
                "total_energy_j": total_energy,
                "energy_per_token_j": (
                    total_energy / total_tokens if total_tokens > 0 else 0
                ),
                "avg_power_w": (
                    total_energy / total_latency if total_latency > 0 else 0
                ),
                "cpu_temp_c": None,
                "gpu_temp_c": None,
            }
        finally:
            agg.close()
    except Exception as exc:
        return {"error": str(exc)}


# ---- Skills routes ----

skills_router = APIRouter(prefix="/v1/skills", tags=["skills"])


@skills_router.get("")
async def list_skills(request: Request):
    """List installed skills."""
    try:
        from openjarvis.core.registry import SkillRegistry

        skills = []
        for key in sorted(SkillRegistry.keys()):
            skills.append({"name": key})
        return {"skills": skills}
    except Exception as exc:
        logger.warning("Failed to list skills: %s", exc)
        return {"skills": []}


@skills_router.post("")
async def install_skill(request: Request):
    """Install a skill (placeholder)."""
    return {
        "status": "not_implemented",
        "message": "Use TOML files in ~/.openjarvis/skills/",
    }


@skills_router.delete("/{skill_name}")
async def remove_skill(skill_name: str, request: Request):
    """Remove a skill (placeholder)."""
    return {
        "status": "not_implemented",
        "message": "Skill removal not yet supported via API",
    }


# ---- Sessions routes ----

sessions_router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@sessions_router.get("")
async def list_sessions(request: Request, limit: int = 20):
    """List active sessions."""
    try:
        from openjarvis.sessions.store import SessionStore

        store = SessionStore()
        sessions = store.recent(limit=limit)
        items = [s.to_dict() if hasattr(s, "to_dict") else str(s) for s in sessions]
        return {"sessions": items}
    except Exception as exc:
        return {"sessions": [], "error": str(exc)}


@sessions_router.get("/{session_id}")
async def get_session(session_id: str, request: Request):
    """Get a specific session."""
    try:
        from openjarvis.sessions.store import SessionStore

        store = SessionStore()
        session = store.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return session.to_dict() if hasattr(session, "to_dict") else {"id": session_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---- Budget routes ----

budget_router = APIRouter(prefix="/v1/budget", tags=["budget"])

_budget_limits: Dict[str, Any] = {
    "max_tokens_per_day": None,
    "max_requests_per_hour": None,
}
_budget_usage: Dict[str, int] = {
    "tokens_today": 0,
    "requests_this_hour": 0,
}


@budget_router.get("")
async def get_budget(request: Request):
    """Get current budget usage and limits."""
    return {"limits": _budget_limits, "usage": _budget_usage}


@budget_router.put("/limits")
async def set_budget_limits(req: BudgetLimitsRequest, request: Request):
    """Update budget limits."""
    if req.max_tokens_per_day is not None:
        _budget_limits["max_tokens_per_day"] = req.max_tokens_per_day
    if req.max_requests_per_hour is not None:
        _budget_limits["max_requests_per_hour"] = req.max_requests_per_hour
    return {"status": "updated", "limits": _budget_limits}


# ---- Prometheus metrics ----

metrics_router = APIRouter(tags=["metrics"])


@metrics_router.get("/metrics")
async def prometheus_metrics(request: Request):
    """Prometheus-compatible metrics endpoint."""
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR
        from openjarvis.telemetry.aggregator import TelemetryAggregator

        db_path = DEFAULT_CONFIG_DIR / "telemetry.db"
        if not db_path.exists():
            from starlette.responses import PlainTextResponse

            return PlainTextResponse("# no telemetry data\n", media_type="text/plain")

        agg = TelemetryAggregator(db_path)
        stats = agg.summary()

        lines = [
            "# HELP openjarvis_requests_total Total requests processed",
            "# TYPE openjarvis_requests_total counter",
            f"openjarvis_requests_total {stats.get('total_requests', 0)}",
            "# HELP openjarvis_tokens_total Total tokens generated",
            "# TYPE openjarvis_tokens_total counter",
            f"openjarvis_tokens_total {stats.get('total_tokens', 0)}",
            "# HELP openjarvis_latency_avg_ms Average latency in milliseconds",
            "# TYPE openjarvis_latency_avg_ms gauge",
            f"openjarvis_latency_avg_ms {stats.get('avg_latency_ms', 0)}",
        ]
        from starlette.responses import PlainTextResponse

        return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")
    except Exception as exc:
        logger.warning("Failed to collect Prometheus metrics: %s", exc)
        from starlette.responses import PlainTextResponse

        return PlainTextResponse("# No metrics available\n", media_type="text/plain")


# ---- WebSocket streaming routes ----

websocket_router = APIRouter(tags=["websocket"])


@websocket_router.websocket("/v1/chat/stream")
async def websocket_chat_stream(websocket: WebSocket):
    """Stream chat responses over a WebSocket connection.

    Accepts JSON messages of the form::

        {"message": "...", "model": "...", "agent": "..."}

    Sends back JSON chunks::

        {"type": "chunk", "content": "..."}   -- per-token streaming
        {"type": "done",  "content": "..."}   -- final assembled response
        {"type": "error", "detail": "..."}    -- on failure
    """
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                await websocket.send_json(
                    {"type": "error", "detail": "Invalid JSON"},
                )
                continue

            message = data.get("message")
            if not message:
                await websocket.send_json(
                    {"type": "error", "detail": "Missing 'message' field"},
                )
                continue

            model = data.get("model") or getattr(
                websocket.app.state,
                "model",
                "default",
            )
            engine = getattr(websocket.app.state, "engine", None)
            if engine is None:
                await websocket.send_json(
                    {"type": "error", "detail": "No engine configured"},
                )
                continue

            messages = [{"role": "user", "content": message}]

            try:
                # Prefer streaming if the engine supports it
                stream_fn = getattr(engine, "stream", None)
                if stream_fn is not None and (
                    inspect.isasyncgenfunction(stream_fn) or callable(stream_fn)
                ):
                    full_content = ""
                    try:
                        gen = stream_fn(messages, model=model)
                        # Handle both async and sync generators
                        if inspect.isasyncgen(gen):
                            async for token in gen:
                                full_content += token
                                await websocket.send_json(
                                    {"type": "chunk", "content": token},
                                )
                        else:
                            # Sync generator — iterate in a thread to avoid
                            # blocking the event loop
                            for token in gen:
                                full_content += token
                                await websocket.send_json(
                                    {"type": "chunk", "content": token},
                                )
                    except TypeError:
                        # stream() didn't return an iterable; fall back to
                        # generate()
                        result = engine.generate(messages, model=model)
                        content = (
                            result.get("content", "")
                            if isinstance(
                                result,
                                dict,
                            )
                            else str(result)
                        )
                        full_content = content
                        await websocket.send_json(
                            {"type": "chunk", "content": content},
                        )
                    await websocket.send_json(
                        {"type": "done", "content": full_content},
                    )
                else:
                    # No stream method — single-shot generate
                    result = engine.generate(messages, model=model)
                    content = (
                        result.get("content", "")
                        if isinstance(
                            result,
                            dict,
                        )
                        else str(result)
                    )
                    await websocket.send_json(
                        {"type": "chunk", "content": content},
                    )
                    await websocket.send_json(
                        {"type": "done", "content": content},
                    )
            except WebSocketDisconnect:
                raise
            except Exception as exc:
                await websocket.send_json(
                    {"type": "error", "detail": str(exc)},
                )
    except WebSocketDisconnect:
        pass  # Client disconnected — nothing to clean up


# ---- Learning routes ----

learning_router = APIRouter(prefix="/v1/learning", tags=["learning"])


@learning_router.get("/stats")
async def learning_stats(request: Request):
    """Return learning system statistics across all sub-policies."""
    result: Dict[str, Any] = {}

    # Skill discovery
    try:
        from openjarvis.learning.agents.skill_discovery import SkillDiscovery

        discovery = SkillDiscovery()
        result["skill_discovery"] = {
            "available": True,
            "discovered_count": len(discovery.discovered_skills),
        }
    except Exception as exc:
        logger.warning("Failed to load skill discovery stats: %s", exc)
        result["skill_discovery"] = {"available": False}

    return result


@learning_router.get("/policy")
async def learning_policy(request: Request):
    """Return current routing policy configuration."""
    result: Dict[str, Any] = {}

    # Load config and extract learning section
    try:
        from openjarvis.core.config import load_config

        config = load_config()
        lc = config.learning
        result["enabled"] = lc.enabled
        result["update_interval"] = lc.update_interval
        result["auto_update"] = lc.auto_update
        result["routing"] = {
            "policy": lc.routing.policy,
            "min_samples": lc.routing.min_samples,
        }
        result["intelligence"] = {
            "policy": lc.intelligence.policy,
        }
        result["agent"] = {
            "policy": lc.agent.policy,
        }
        result["metrics"] = {
            "accuracy_weight": lc.metrics.accuracy_weight,
            "latency_weight": lc.metrics.latency_weight,
            "cost_weight": lc.metrics.cost_weight,
            "efficiency_weight": lc.metrics.efficiency_weight,
        }
    except Exception as exc:
        logger.warning("Failed to load learning config: %s", exc)
        result["enabled"] = False
        result["routing"] = {"policy": "heuristic", "min_samples": 5}
        result["intelligence"] = {"policy": "none"}
        result["agent"] = {"policy": "none"}
        result["metrics"] = {}

    return result


# ---- Speech routes ----

speech_router = APIRouter(prefix="/v1/speech", tags=["speech"])


@speech_router.post("/transcribe")
async def transcribe_speech(request: Request):
    """Transcribe uploaded audio to text."""
    backend = getattr(request.app.state, "speech_backend", None)
    if backend is None:
        raise HTTPException(status_code=501, detail="Speech backend not configured")

    form = await request.form()
    audio_file = form.get("file")
    if audio_file is None:
        raise HTTPException(status_code=400, detail="Missing 'file' field")

    audio_bytes = await audio_file.read()
    language = form.get("language")

    # Detect format from filename
    filename = getattr(audio_file, "filename", "audio.wav")
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "wav"

    result = backend.transcribe(audio_bytes, format=ext, language=language or None)
    return {
        "text": result.text,
        "language": result.language,
        "confidence": result.confidence,
        "duration_seconds": result.duration_seconds,
    }


@speech_router.get("/health")
async def speech_health(request: Request):
    """Check if a speech backend is available."""
    backend = getattr(request.app.state, "speech_backend", None)
    if backend is None:
        return {"available": False, "reason": "No speech backend configured"}
    return {
        "available": backend.health(),
        "backend": backend.backend_id,
    }


# ---- Voice push-to-talk routes ----

voice_router = APIRouter(prefix="/v1/voice/ptt", tags=["voice"])


def _get_voice_ptt_service(request: Request):
    service = getattr(request.app.state, "voice_ptt_service", None)
    if service is not None:
        return service

    from openjarvis.agent_workspace import AgentWorkspaceRegistry
    from openjarvis.security.approval_queue import ApprovalQueue
    from openjarvis.security.permissions import PermissionMiddleware
    from openjarvis.voice import VoicePushToTalkService

    config = getattr(request.app.state, "config", None)
    mode_registry = getattr(request.app.state, "mode_registry", None)
    workspace_registry = getattr(
        request.app.state,
        "agent_workspace_registry",
        None,
    )
    if workspace_registry is None:
        workspace_registry = AgentWorkspaceRegistry()
        request.app.state.agent_workspace_registry = workspace_registry
    permission_middleware = getattr(
        request.app.state,
        "permission_middleware",
        None,
    )
    if permission_middleware is None:
        permission_middleware = PermissionMiddleware(mode_registry=mode_registry)
        request.app.state.permission_middleware = permission_middleware
    approval_queue = getattr(request.app.state, "approval_queue", None)
    if approval_queue is None:
        approval_queue = ApprovalQueue()
        request.app.state.approval_queue = approval_queue
    service = VoicePushToTalkService(
        config=config,
        speech_backend=getattr(request.app.state, "speech_backend", None),
        permission_middleware=permission_middleware,
        approval_queue=approval_queue,
        mode_registry=mode_registry,
        agent_workspace_registry=workspace_registry,
        context_layer=getattr(request.app.state, "context_layer", None),
        memory_service=getattr(request.app.state, "structured_memory_service", None),
    )
    request.app.state.voice_ptt_service = service
    return service


def _voice_error(exc: Exception) -> HTTPException:
    from openjarvis.voice import VoicePermissionError, VoiceRecordingError

    if isinstance(exc, VoicePermissionError):
        return HTTPException(
            status_code=403,
            detail={"status": "blocked", "reason": str(exc)},
        )
    if isinstance(exc, VoiceRecordingError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@voice_router.post("/start")
async def start_voice_recording(req: VoiceStartRecordingRequest, request: Request):
    """Start explicit push-to-talk microphone recording."""
    service = _get_voice_ptt_service(request)
    try:
        session = service.start_recording(
            agent_id=req.agent_id,
            explicit_approval=req.approved,
            persist_raw_audio=req.persist_raw_audio,
        )
        return {
            "status": service.status(),
            "session": session.to_dict(),
            "recording": session.to_dict(),
        }
    except Exception as exc:
        raise _voice_error(exc) from exc


@voice_router.post("/stop")
async def stop_voice_recording(request: Request):
    """Stop the active push-to-talk recording."""
    service = _get_voice_ptt_service(request)
    try:
        session = service.stop_recording()
        return {
            "status": service.status(),
            "session": session.to_dict(),
            "recording": session.to_dict(),
        }
    except Exception as exc:
        raise _voice_error(exc) from exc


@voice_router.get("/status")
async def voice_recording_status(request: Request):
    """Return push-to-talk recording status."""
    return _get_voice_ptt_service(request).status()


@voice_router.post("/transcribe-latest")
async def transcribe_latest_voice(
    req: VoiceTranscribeLatestRequest,
    request: Request,
):
    """Transcribe the latest stopped recording with a local backend."""
    service = _get_voice_ptt_service(request)
    try:
        return service.transcribe_latest(language=req.language or None)
    except Exception as exc:
        raise _voice_error(exc) from exc


# ---- Global voice hotkey routes ----

hotkey_router = APIRouter(prefix="/v1/hotkeys", tags=["hotkeys"])


def _get_hotkey_service(request: Request):
    service = getattr(request.app.state, "hotkey_service", None)
    if service is not None:
        return service

    from openjarvis.hotkeys import GlobalVoiceHotkeyService
    from openjarvis.security.permissions import PermissionMiddleware

    mode_registry = getattr(request.app.state, "mode_registry", None)
    permission_middleware = getattr(
        request.app.state,
        "permission_middleware",
        None,
    )
    if permission_middleware is None:
        permission_middleware = PermissionMiddleware(mode_registry=mode_registry)
        request.app.state.permission_middleware = permission_middleware

    service = GlobalVoiceHotkeyService(
        config=getattr(request.app.state, "config", None),
        voice_service=_get_voice_ptt_service(request),
        tts_service=getattr(request.app.state, "tts_service", None),
        permission_middleware=permission_middleware,
        mode_registry=mode_registry,
        desktop_service=getattr(request.app.state, "desktop_service", None),
    )
    request.app.state.hotkey_service = service
    return service


def _hotkey_error(exc: Exception) -> HTTPException:
    from openjarvis.hotkeys import HotkeyListenerUnavailableError, HotkeyPermissionError

    if isinstance(exc, HotkeyPermissionError):
        return HTTPException(
            status_code=403,
            detail={"status": "blocked", "reason": str(exc)},
        )
    if isinstance(exc, HotkeyListenerUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@hotkey_router.get("/status")
async def hotkey_status(request: Request):
    """Return global voice trigger status."""
    return _get_hotkey_service(request).status()


@hotkey_router.post("/enable")
async def enable_hotkey(req: HotkeyEnableRequest, request: Request):
    """Enable explicit system-level voice trigger listening."""
    service = _get_hotkey_service(request)
    try:
        binding = None
        if req.binding or req.fallback:
            from openjarvis.hotkeys import HotkeyBinding

            current = service.current_binding()
            binding = HotkeyBinding.from_config(
                getattr(request.app.state, "config", None)
            )
            if req.binding:
                binding.keys = [
                    part.strip().lower().replace("control", "ctrl")
                    for part in req.binding.replace("-", "+").split("+")
                    if part.strip()
                ]
                binding.display_name = "+".join(part.title() for part in binding.keys)
                binding.kind = "fn_hold" if binding.keys == ["fn"] else "hotkey_hold"
            if req.fallback:
                binding.fallback_keys = [
                    part.strip().lower().replace("control", "ctrl")
                    for part in req.fallback.replace("-", "+").split("+")
                    if part.strip()
                ]
                binding.fallback_display_name = "+".join(
                    part.title() for part in binding.fallback_keys
                )
            if not req.binding and current.get("keys"):
                binding.keys = list(current["keys"])
            if not req.fallback and current.get("fallback_keys"):
                binding.fallback_keys = list(current["fallback_keys"])
        return service.enable(binding=binding, explicit_approval=req.approved)
    except Exception as exc:
        raise _hotkey_error(exc) from exc


@hotkey_router.post("/disable")
async def disable_hotkey(request: Request):
    """Disable global voice trigger listening."""
    try:
        return _get_hotkey_service(request).disable()
    except Exception as exc:
        raise _hotkey_error(exc) from exc


@hotkey_router.get("/binding")
async def hotkey_binding(request: Request):
    """Return the current voice trigger binding."""
    return _get_hotkey_service(request).current_binding()


@hotkey_router.post("/test-trigger")
async def test_hotkey_trigger(req: HotkeyTestTriggerRequest, request: Request):
    """Test the hotkey route without opening the microphone."""
    try:
        return _get_hotkey_service(request).test_trigger(
            explicit_approval=req.approved
        )
    except Exception as exc:
        raise _hotkey_error(exc) from exc


# ---- Local voice output routes ----

tts_router = APIRouter(prefix="/v1/tts", tags=["tts"])


def _get_tts_service(request: Request):
    service = getattr(request.app.state, "tts_service", None)
    if service is not None:
        return service

    from openjarvis.agent_workspace import AgentWorkspaceRegistry
    from openjarvis.security.permissions import PermissionMiddleware
    from openjarvis.tts import LocalTTSService

    mode_registry = getattr(request.app.state, "mode_registry", None)
    workspace_registry = getattr(
        request.app.state,
        "agent_workspace_registry",
        None,
    )
    if workspace_registry is None:
        workspace_registry = AgentWorkspaceRegistry()
        request.app.state.agent_workspace_registry = workspace_registry
    permission_middleware = getattr(
        request.app.state,
        "permission_middleware",
        None,
    )
    if permission_middleware is None:
        permission_middleware = PermissionMiddleware(mode_registry=mode_registry)
        request.app.state.permission_middleware = permission_middleware

    service = LocalTTSService(
        permission_middleware=permission_middleware,
        mode_registry=mode_registry,
        agent_workspace_registry=workspace_registry,
        context_layer=getattr(request.app.state, "context_layer", None),
        memory_service=getattr(request.app.state, "structured_memory_service", None),
        voice_service=getattr(request.app.state, "voice_ptt_service", None),
    )
    request.app.state.tts_service = service
    return service


def _tts_error(exc: Exception) -> HTTPException:
    from openjarvis.tts import TTSPermissionError, TTSUnavailableError

    if isinstance(exc, TTSPermissionError):
        return HTTPException(
            status_code=403,
            detail={"status": "blocked", "reason": str(exc)},
        )
    if isinstance(exc, TTSUnavailableError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@tts_router.post("/speak")
async def speak_tts(req: TTSSpeakApiRequest, request: Request):
    """Speak text through a local-only TTS engine."""
    service = _get_tts_service(request)
    try:
        speech = service.speak(
            req.text,
            voice_id=req.voice_id,
            engine=req.engine,
            user_triggered=req.user_triggered,
            allow_quiet=req.allow_quiet,
            speed=req.speed,
        )
        return {"status": service.status(), "speech": speech.to_dict()}
    except Exception as exc:
        raise _tts_error(exc) from exc


@tts_router.post("/stop")
async def stop_tts(request: Request):
    """Stop active local voice output."""
    service = _get_tts_service(request)
    try:
        speech = service.stop()
        return {
            "status": service.status(),
            "speech": speech.to_dict() if speech is not None else None,
        }
    except Exception as exc:
        raise _tts_error(exc) from exc


@tts_router.get("/status")
async def tts_status(request: Request):
    """Return local voice output status."""
    return _get_tts_service(request).status()


@tts_router.get("/voices")
async def tts_voices(request: Request):
    """List local voice output voices."""
    voices = _get_tts_service(request).voices()
    return {
        "local_only": True,
        "cloud_tts_enabled": False,
        "voices": [voice.to_dict() for voice in voices],
    }


# ---- Feedback routes ----

feedback_router = APIRouter(prefix="/v1/feedback", tags=["feedback"])


@feedback_router.post("")
async def submit_feedback(req: FeedbackScoreRequest, request: Request):
    """Submit feedback for a trace."""
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR
        from openjarvis.traces.store import TraceStore

        db_path = DEFAULT_CONFIG_DIR / "traces.db"
        if not db_path.exists():
            raise HTTPException(status_code=404, detail="No trace database")

        store = TraceStore(db_path)
        updated = store.update_feedback(req.trace_id, req.score)
        store.close()

        if not updated:
            raise HTTPException(
                status_code=404, detail=f"Trace '{req.trace_id}' not found"
            )
        return {"status": "recorded", "trace_id": req.trace_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@feedback_router.get("/stats")
async def feedback_stats(request: Request):
    """Get feedback statistics."""
    return {"total": 0, "mean_score": 0.0}


# ---- Optimize routes ----

optimize_router = APIRouter(prefix="/v1/optimize", tags=["optimize"])


@optimize_router.get("/runs")
async def list_optimize_runs(request: Request):
    """List optimization runs."""
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR
        from openjarvis.learning.optimize.store import OptimizationStore

        db_path = DEFAULT_CONFIG_DIR / "optimize.db"
        if not db_path.exists():
            return {"runs": []}

        store = OptimizationStore(db_path)
        runs = store.list_runs()
        store.close()
        return {"runs": runs}
    except Exception as exc:
        logger.warning("Failed to list optimization runs: %s", exc)
        return {"runs": []}


@optimize_router.get("/runs/{run_id}")
async def get_optimize_run(run_id: str, request: Request):
    """Get optimization run details."""
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR
        from openjarvis.learning.optimize.store import OptimizationStore

        db_path = DEFAULT_CONFIG_DIR / "optimize.db"
        if not db_path.exists():
            return {"run_id": run_id, "status": "not_found"}

        store = OptimizationStore(db_path)
        run = store.get_run(run_id)
        store.close()

        if run is None:
            return {"run_id": run_id, "status": "not_found"}

        return {
            "run_id": run.run_id,
            "status": run.status,
            "benchmark": run.benchmark,
            "trials": len(run.trials),
            "best_trial_id": (run.best_trial.trial_id if run.best_trial else None),
        }
    except Exception as exc:
        logger.warning("Failed to get optimization run %s: %s", run_id, exc)
        return {"run_id": run_id, "status": "not_found"}


@optimize_router.post("/runs")
async def start_optimize_run(req: OptimizeRunRequest, request: Request):
    """Start a new optimization run."""
    return {"status": "started", "run_id": "placeholder"}


def include_all_routes(app) -> None:
    """Include all extended API routers in a FastAPI app."""
    app.include_router(agents_router)
    app.include_router(memory_router)
    app.include_router(traces_router)
    app.include_router(telemetry_router)
    app.include_router(skills_router)
    app.include_router(sessions_router)
    app.include_router(budget_router)
    app.include_router(metrics_router)
    app.include_router(websocket_router)
    app.include_router(learning_router)
    app.include_router(speech_router)
    app.include_router(voice_router)
    app.include_router(hotkey_router)
    app.include_router(tts_router)
    app.include_router(feedback_router)
    app.include_router(optimize_router)
    app.include_router(agent_workspace_router)
    app.include_router(mode_router)
    app.include_router(morning_briefing_router)
    app.include_router(startup_router)
    app.include_router(worldmonitor_router)
    app.include_router(notification_router)
    app.include_router(packaging_router)
    app.include_router(research_router)
    app.include_router(context_router)
    app.include_router(desktop_router)
    app.include_router(engineering_router)
    app.include_router(repo_index_router)
    app.include_router(coding_assistant_router)
    app.include_router(workflow_router)

    # Agent Manager routes (if available)
    try:
        if hasattr(app.state, "agent_manager") and app.state.agent_manager:
            from openjarvis.server.agent_manager_routes import (  # noqa: PLC0415
                create_agent_manager_router,
            )

            (
                agents_r,
                templates_r,
                global_r,
                tools_r,
                sendblue_r,
            ) = create_agent_manager_router(app.state.agent_manager)
            app.include_router(agents_r)
            app.include_router(templates_r)
            app.include_router(global_r)
            app.include_router(tools_r)
            app.include_router(sendblue_r)
    except ImportError:
        pass

    # WebSocket bridge for real-time agent events
    try:
        from openjarvis.core.events import get_event_bus
        from openjarvis.server.ws_bridge import create_ws_router

        ws_router = create_ws_router(get_event_bus())
        app.include_router(ws_router)
    except Exception:
        logger.debug("WebSocket bridge not available", exc_info=True)


__all__ = [
    "include_all_routes",
    "agents_router",
    "memory_router",
    "traces_router",
    "telemetry_router",
    "skills_router",
    "sessions_router",
    "budget_router",
    "metrics_router",
    "websocket_router",
    "learning_router",
    "speech_router",
    "voice_router",
    "hotkey_router",
    "tts_router",
    "feedback_router",
    "optimize_router",
    "agent_workspace_router",
    "coding_assistant_router",
    "mode_router",
    "packaging_router",
    "repo_index_router",
    "research_router",
    "workflow_router",
]
