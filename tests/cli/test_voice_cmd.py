"""Tests for the local typed/mock voice CLI bridge."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from click.testing import CliRunner


def _load_voice_cmd_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "openjarvis"
        / "cli"
        / "voice_cmd.py"
    )
    spec = importlib.util.spec_from_file_location("voice_cmd_under_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


voice_cmd = _load_voice_cmd_module()


def _preview_response() -> dict[str, Any]:
    return {
        "status": "awaiting_approval",
        "fsm_state": "awaiting_approval",
        "transcript": "open notes",
        "intent_preview": {
            "interpreted_intent": "action_request",
            "risk_level": "medium",
            "approval_required": True,
            "planned_actions": [
                "preview transcript",
                "request explicit approval before execution",
            ],
        },
        "approved": False,
        "dispatched": False,
    }


def test_voice_command_help_lists_subcommands() -> None:
    result = CliRunner().invoke(voice_cmd.voice, ["--help"])

    assert result.exit_code == 0
    assert "submit" in result.output
    assert "cancel" in result.output


def test_voice_submit_previews_without_dispatch(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        calls.append((endpoint, payload))
        return _preview_response()

    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(voice_cmd.voice, ["submit", "open", "notes"])

    assert result.exit_code == 0
    assert calls == [
        (
            "/v1/voice/ptt/submit-transcript",
            {"transcript": "open notes", "session_id": ""},
        )
    ]
    assert "Voice transcript preview" in result.output
    assert "dispatch: skipped" in result.output


def test_voice_submit_dispatches_only_with_approval_flag(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        calls.append((endpoint, payload))
        if endpoint.endswith("/submit-transcript"):
            return _preview_response()
        return {
            "dispatched": True,
            "status": "completed",
            "fsm_state": "idle",
            "agent_id": "agent-1",
        }

    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(
        voice_cmd.voice,
        [
            "submit",
            "open",
            "notes",
            "--agent-id",
            "agent-1",
            "--approve-dispatch",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        (
            "/v1/voice/ptt/submit-transcript",
            {"transcript": "open notes", "session_id": ""},
        ),
        (
            "/v1/voice/ptt/dispatch",
            {"transcript": "open notes", "agent_id": "agent-1", "approved": True},
        ),
    ]
    assert "Voice dispatch result" in result.output
    assert "dispatched: True" in result.output


def test_voice_cancel_calls_cancel_endpoint(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, Any] | None]] = []

    def fake_post(endpoint: str, payload: dict[str, Any] | None, **kwargs):
        calls.append((endpoint, payload))
        return {"fsm_state": "idle"}

    monkeypatch.setattr(voice_cmd, "_post_json", fake_post)
    monkeypatch.setattr(voice_cmd, "_base_url", lambda override: "http://test")
    monkeypatch.setattr(voice_cmd, "_api_key", lambda override: "")

    result = CliRunner().invoke(voice_cmd.voice, ["cancel"])

    assert result.exit_code == 0
    assert calls == [("/v1/voice/ptt/cancel", {})]
    assert "idle" in result.output
