from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.core.config import JarvisConfig  # noqa: E402
from openjarvis.server.api_routes import voice_router  # noqa: E402
from openjarvis.voice.event_log import (  # noqa: E402
    VoiceEventLogger,
    voice_log_settings_from_config,
)
from openjarvis.voice.models import TranscriptionUnavailableError  # noqa: E402
from openjarvis.voice.ptt import RecordingHandle, VoicePushToTalkService  # noqa: E402


class FakeRecorder:
    def __init__(self, tmp_path: Path) -> None:
        self.path = tmp_path / "recording.wav"

    def start(self, recording_id: str) -> RecordingHandle:
        self.path.write_bytes(b"recording")
        return RecordingHandle(recording_id=recording_id, path=self.path, format="wav")

    def stop(self, handle: RecordingHandle) -> None:
        handle.path.write_bytes(b"recording stopped")


class FakeBackend:
    backend_id = "faster-whisper"

    def health(self) -> bool:
        return True

    def supported_formats(self):
        return ["wav"]

    def transcribe(self, audio: bytes, *, format: str = "wav", language=None):
        return type(
            "Result",
            (),
            {
                "text": "phase one transcript",
                "language": "en",
                "confidence": None,
                "duration_seconds": 0.0,
                "segments": [],
            },
        )


class FakeDecision:
    action = "require_confirmation"
    level = type("Level", (), {"name": "CONFIRMED_EXECUTION"})()
    denied = False
    requires_confirmation = True
    reason = "tool requires confirmation"
    matched_pattern = None


class FakePermissionMiddleware:
    def check(self, request):
        return FakeDecision()


class FakeUnavailableTranscriber:
    def available(self) -> bool:
        return False

    def transcribe(self, *args, **kwargs):
        raise TranscriptionUnavailableError("transcription backend unavailable")


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = FastAPI()
    config = JarvisConfig()
    config.voice_control.voice_logs_enabled = False
    config.voice_control.voice_logs_path = str(tmp_path / "voice-events.jsonl")
    service = VoicePushToTalkService(
        config=config,
        speech_backend=FakeBackend(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )
    app.state.voice_ptt_service = service
    app.include_router(voice_router)
    return TestClient(app)


def test_voice_status_is_push_to_talk_only(client: TestClient) -> None:
    resp = client.get("/v1/voice/ptt/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["push_to_talk_only"] is True
    assert data["wake_word_enabled"] is False
    assert data["passive_listening"] is False
    assert data["fsm_state"] == "idle"
    assert data["voice_stack"]["safety"]["always_on_listening"] is False
    assert data["voice_stack"]["hotkey_bridge"]["print_only"] is True
    assert data["voice_stack"]["hotkey_bridge"]["enabled"] is False
    assert data["voice_stack"]["approval"]["required"] is True


def test_voice_status_includes_safe_stack_config(client: TestClient) -> None:
    resp = client.get("/v1/voice/ptt/status")

    assert resp.status_code == 200
    stack = resp.json()["voice_stack"]
    assert stack["api_base_url"] == {
        "value": "http://127.0.0.1:8000",
        "source": "[server].host/[server].port",
    }
    assert stack["transcription_adapter"]["effective"] == "disabled"
    assert stack["model_path"]["source"] == "[speech].model"
    assert stack["record_duration"]["duration_flag_required"] is True
    assert stack["speech_output"]["backend"] == "macos-say"
    assert "path" in stack["macos_say"]
    assert stack["safety"]["dispatch_called"] is False
    assert stack["safety"]["speech_called"] is False
    assert stack["safety"]["approval_bypassed"] is False
    assert stack["recent_events"]["events"] == []


def test_voice_status_includes_configured_api_base_url(tmp_path: Path) -> None:
    app = FastAPI()
    config = JarvisConfig()
    config.voice_control.default_api_base_url = "http://configured:9000/"
    config.voice_control.voice_logs_enabled = False
    config.voice_control.voice_logs_path = str(tmp_path / "voice-events.jsonl")
    service = VoicePushToTalkService(
        config=config,
        speech_backend=FakeBackend(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )
    app.state.voice_ptt_service = service
    app.include_router(voice_router)

    resp = TestClient(app).get("/v1/voice/ptt/status")

    assert resp.status_code == 200
    assert resp.json()["voice_stack"]["api_base_url"] == {
        "value": "http://configured:9000",
        "source": "[voice_control].default_api_base_url",
    }


def test_voice_status_recent_events_are_redacted(tmp_path: Path) -> None:
    app = FastAPI()
    config = JarvisConfig()
    config.voice_control.voice_logs_enabled = True
    config.voice_control.voice_logs_path = str(tmp_path / "voice-events.jsonl")
    config.voice_control.voice_logs_include_full_transcripts = False
    config.voice_control.voice_logs_preview_chars = 120
    logger = VoiceEventLogger(voice_log_settings_from_config(config))
    logger.record(
        command="capture-preview",
        event="preview_result",
        transcript="email me at luca@example.com with token-123456789",
        details={
            "recording_path": str(tmp_path / "voice.wav"),
            "dispatch_skipped": True,
            "approved": False,
        },
    )
    service = VoicePushToTalkService(
        config=config,
        speech_backend=FakeBackend(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )
    app.state.voice_ptt_service = service
    app.include_router(voice_router)

    resp = TestClient(app).get("/v1/voice/ptt/status")

    assert resp.status_code == 200
    events = resp.json()["voice_stack"]["recent_events"]["events"]
    assert len(events) == 1
    event = events[0]
    assert event["transcript"]["preview"] == "email me at [email] with [secret]"
    assert event["transcript"]["full_transcript_logged"] is False
    assert "text" not in event["transcript"]
    assert "recording_path" not in event["details"]
    assert event["details"] == {"dispatch_skipped": True, "approved": False}


def test_voice_start_requires_approval(client: TestClient) -> None:
    resp = client.post("/v1/voice/ptt/start", json={})

    assert resp.status_code == 403
    assert resp.json()["detail"]["status"] == "blocked"


def test_voice_start_stop_transcribe_latest(client: TestClient) -> None:
    start = client.post("/v1/voice/ptt/start", json={"approved": True})
    assert start.status_code == 200
    assert start.json()["status"]["recording"] is True
    assert start.json()["session"]["status"] == "recording"

    stop = client.post("/v1/voice/ptt/stop")
    assert stop.status_code == 200
    assert stop.json()["status"]["recording"] is False
    assert stop.json()["session"]["status"] == "recorded"

    transcript = client.post("/v1/voice/ptt/transcribe-latest", json={})
    assert transcript.status_code == 200
    data = transcript.json()
    assert data["text"] == "phase one transcript"
    assert data["intent_preview"]["interpreted_intent"] == "dictation"
    assert data["session"]["status"] == "preview_ready"
    assert data["dispatched_to_agent"] is False


def test_voice_dispatch_requires_approval(client: TestClient) -> None:
    resp = client.post(
        "/v1/voice/ptt/dispatch",
        json={"transcript": "open the notes app", "approved": False},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["status"] == "approval_required"


def test_voice_dispatch_no_approval_field_also_blocked(client: TestClient) -> None:
    resp = client.post(
        "/v1/voice/ptt/dispatch",
        json={"transcript": "open the notes app"},
    )
    assert resp.status_code == 403


def test_voice_dispatch_no_agent_returns_not_dispatched(client: TestClient) -> None:
    resp = client.post(
        "/v1/voice/ptt/dispatch",
        json={"transcript": "open the notes app", "approved": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["dispatched"] is False
    assert "agent" in data["reason"]


def test_voice_dispatch_empty_transcript_is_422(client: TestClient) -> None:
    resp = client.post(
        "/v1/voice/ptt/dispatch",
        json={"transcript": "  ", "approved": True},
    )
    assert resp.status_code == 422


def test_voice_dispatch_with_mocked_agent(tmp_path: Path) -> None:
    import sys
    import types

    fake_result = types.SimpleNamespace(success=True, content="queued")
    fake_tool = types.SimpleNamespace(execute=lambda **kw: fake_result)
    fake_module = types.ModuleType("openjarvis.tools.agent_tools")
    fake_module.AgentSendTool = lambda: fake_tool  # type: ignore[attr-defined]

    app = FastAPI()
    service = VoicePushToTalkService(
        config=JarvisConfig(),
        recorder=FakeRecorder(tmp_path),
        speech_backend=FakeBackend(),
        permission_middleware=FakePermissionMiddleware(),
    )
    app.state.voice_ptt_service = service
    app.state.active_agent_id = "agent-test-123"
    app.include_router(voice_router)

    saved = sys.modules.get("openjarvis.tools.agent_tools")
    sys.modules["openjarvis.tools.agent_tools"] = fake_module
    try:
        c = TestClient(app)
        resp = c.post(
            "/v1/voice/ptt/dispatch",
            json={
                "transcript": "summarise my notes",
                "agent_id": "agent-test-123",
                "approved": True,
            },
        )
    finally:
        if saved is None:
            sys.modules.pop("openjarvis.tools.agent_tools", None)
        else:
            sys.modules["openjarvis.tools.agent_tools"] = saved

    assert resp.status_code == 200
    data = resp.json()
    assert data["dispatched"] is True
    assert data["status"] == "completed"
    assert data["fsm_state"] == "idle"
    assert data["completion_fsm_state"] == "idle"
    assert data["agent_id"] == "agent-test-123"
    assert data["transcript"] == "summarise my notes"


def test_voice_dispatch_after_preview_completes_then_resets(tmp_path: Path) -> None:
    import sys
    import types

    fake_result = types.SimpleNamespace(success=True, content="queued")
    fake_tool = types.SimpleNamespace(execute=lambda **kw: fake_result)
    fake_module = types.ModuleType("openjarvis.tools.agent_tools")
    fake_module.AgentSendTool = lambda: fake_tool  # type: ignore[attr-defined]

    app = FastAPI()
    service = VoicePushToTalkService(
        config=JarvisConfig(),
        recorder=FakeRecorder(tmp_path),
        speech_backend=FakeBackend(),
        permission_middleware=FakePermissionMiddleware(),
    )
    app.state.voice_ptt_service = service
    app.state.active_agent_id = "agent-test-123"
    app.include_router(voice_router)

    saved = sys.modules.get("openjarvis.tools.agent_tools")
    sys.modules["openjarvis.tools.agent_tools"] = fake_module
    try:
        c = TestClient(app)
        c.post(
            "/v1/voice/ptt/submit-transcript",
            json={"transcript": "summarise my notes"},
        )
        resp = c.post(
            "/v1/voice/ptt/dispatch",
            json={
                "transcript": "summarise my notes",
                "agent_id": "agent-test-123",
                "approved": True,
            },
        )
    finally:
        if saved is None:
            sys.modules.pop("openjarvis.tools.agent_tools", None)
        else:
            sys.modules["openjarvis.tools.agent_tools"] = saved

    assert resp.status_code == 200
    data = resp.json()
    assert data["dispatched"] is True
    assert data["status"] == "completed"
    assert data["completion_fsm_state"] == "completed"
    assert data["fsm_state"] == "idle"


def test_voice_dispatch_failure_moves_fsm_to_failed(tmp_path: Path) -> None:
    import sys
    import types

    fake_result = types.SimpleNamespace(success=False, content="agent rejected")
    fake_tool = types.SimpleNamespace(execute=lambda **kw: fake_result)
    fake_module = types.ModuleType("openjarvis.tools.agent_tools")
    fake_module.AgentSendTool = lambda: fake_tool  # type: ignore[attr-defined]

    app = FastAPI()
    service = VoicePushToTalkService(
        config=JarvisConfig(),
        recorder=FakeRecorder(tmp_path),
        speech_backend=FakeBackend(),
        permission_middleware=FakePermissionMiddleware(),
    )
    app.state.voice_ptt_service = service
    app.state.active_agent_id = "agent-test-123"
    app.include_router(voice_router)

    saved = sys.modules.get("openjarvis.tools.agent_tools")
    sys.modules["openjarvis.tools.agent_tools"] = fake_module
    try:
        c = TestClient(app)
        c.post(
            "/v1/voice/ptt/submit-transcript",
            json={"transcript": "summarise my notes"},
        )
        resp = c.post(
            "/v1/voice/ptt/dispatch",
            json={
                "transcript": "summarise my notes",
                "agent_id": "agent-test-123",
                "approved": True,
            },
        )
    finally:
        if saved is None:
            sys.modules.pop("openjarvis.tools.agent_tools", None)
        else:
            sys.modules["openjarvis.tools.agent_tools"] = saved

    assert resp.status_code == 200
    data = resp.json()
    assert data["dispatched"] is False
    assert data["status"] == "dispatch_failed"
    assert data["fsm_state"] == "failed"
    assert data["error"]["status"] == "dispatch_failed"
    assert "agent rejected" in data["error"]["message"]


def test_submit_transcript_returns_awaiting_approval(client: TestClient) -> None:
    resp = client.post(
        "/v1/voice/ptt/submit-transcript",
        json={"transcript": "what is the weather"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "awaiting_approval"
    assert data["approved"] is False
    assert data["dispatched"] is False
    assert "intent_preview" in data


def test_submit_transcript_empty_is_422(client: TestClient) -> None:
    resp = client.post(
        "/v1/voice/ptt/submit-transcript",
        json={"transcript": ""},
    )
    assert resp.status_code == 422


def test_voice_transcription_unavailable_response(tmp_path: Path) -> None:
    app = FastAPI()
    service = VoicePushToTalkService(
        config=JarvisConfig(),
        transcriber=FakeUnavailableTranscriber(),
        recorder=FakeRecorder(tmp_path),
        permission_middleware=FakePermissionMiddleware(),
    )
    app.state.voice_ptt_service = service
    app.include_router(voice_router)
    client = TestClient(app)

    client.post("/v1/voice/ptt/start", json={"approved": True})
    client.post("/v1/voice/ptt/stop")
    response = client.post("/v1/voice/ptt/transcribe-latest", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "transcription_backend_unavailable"
    assert "transcription backend unavailable" in data["reason"]


def test_submit_transcript_transitions_fsm_state(client: TestClient) -> None:
    resp = client.post(
        "/v1/voice/ptt/submit-transcript",
        json={"transcript": "what is the weather"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fsm_state"] == "awaiting_approval"


def test_cancel_resets_to_idle(client: TestClient) -> None:
    client.post(
        "/v1/voice/ptt/submit-transcript",
        json={"transcript": "run the tests"},
    )
    resp = client.post("/v1/voice/ptt/cancel")
    assert resp.status_code == 200
    assert resp.json()["fsm_state"] == "idle"


def test_cancel_from_idle_is_safe(client: TestClient) -> None:
    resp = client.post("/v1/voice/ptt/cancel")
    assert resp.status_code == 200
    assert resp.json()["fsm_state"] == "idle"


def test_dispatch_includes_fsm_state(client: TestClient) -> None:
    client.post(
        "/v1/voice/ptt/submit-transcript",
        json={"transcript": "run the tests"},
    )
    resp = client.post(
        "/v1/voice/ptt/dispatch",
        json={"transcript": "run the tests", "approved": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "fsm_state" in data
    assert data["fsm_state"] == "idle"


def test_dispatch_without_approval_still_403(client: TestClient) -> None:
    resp = client.post(
        "/v1/voice/ptt/dispatch",
        json={"transcript": "run the tests", "approved": False},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["status"] == "approval_required"
