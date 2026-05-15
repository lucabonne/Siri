"""Tests for permission middleware and ToolExecutor integration."""

from __future__ import annotations

import json
from typing import Any

from openjarvis.core.types import ToolCall, ToolResult
from openjarvis.modes import ModeRegistry
from openjarvis.security.permissions import (
    PermissionLevel,
    PermissionMiddleware,
    PermissionRequest,
)
from openjarvis.tools._stubs import BaseTool, ToolExecutor, ToolSpec


class TestPermissionMiddleware:
    def test_read_only_tool_allowed(self, tmp_path) -> None:
        middleware = PermissionMiddleware(audit_log_path=tmp_path / "permissions.log")
        decision = middleware.check(PermissionRequest(tool_name="file_read"))

        assert decision.action == "allow"
        assert decision.level == PermissionLevel.READ_ONLY

    def test_shell_command_requires_confirmation(self, tmp_path) -> None:
        middleware = PermissionMiddleware(audit_log_path=tmp_path / "permissions.log")
        decision = middleware.check(
            PermissionRequest(
                tool_name="shell_exec",
                arguments={"command": "echo hello"},
            )
        )

        assert decision.action == "require_confirmation"
        assert decision.level == PermissionLevel.CONFIRMED_EXECUTION

    def test_dangerous_shell_command_denied(self, tmp_path) -> None:
        middleware = PermissionMiddleware(audit_log_path=tmp_path / "permissions.log")
        decision = middleware.check(
            PermissionRequest(
                tool_name="shell_exec",
                arguments={"command": "rm -rf /"},
            )
        )

        assert decision.action == "deny"
        assert decision.level == PermissionLevel.DANGEROUS
        assert decision.matched_pattern == "recursive-root-delete"

    def test_mutating_http_requires_confirmation(self, tmp_path) -> None:
        middleware = PermissionMiddleware(audit_log_path=tmp_path / "permissions.log")
        decision = middleware.check(
            PermissionRequest(
                tool_name="http_request",
                arguments={"url": "https://example.com", "method": "DELETE"},
            )
        )

        assert decision.action == "require_confirmation"
        assert decision.level == PermissionLevel.CONFIRMED_EXECUTION

    def test_permission_ceiling_denies_excessive_tool_level(self, tmp_path) -> None:
        middleware = PermissionMiddleware(audit_log_path=tmp_path / "permissions.log")
        decision = middleware.check(
            PermissionRequest(
                tool_name="shell_exec",
                arguments={"command": "echo hello"},
                permission_ceiling=PermissionLevel.SAFE_ACTION,
            )
        )

        assert decision.action == "deny"
        assert decision.level == PermissionLevel.DANGEROUS
        assert decision.matched_pattern == "agent-permission-ceiling"
        assert "exceeds agent ceiling SAFE_ACTION" in decision.reason

    def test_terminal_context_tools_are_classified(self, tmp_path) -> None:
        middleware = PermissionMiddleware(audit_log_path=tmp_path / "permissions.log")

        context_decision = middleware.check(
            PermissionRequest(tool_name="terminal_context")
        )
        approval_decision = middleware.check(
            PermissionRequest(tool_name="terminal_suggested_command_approval")
        )

        assert context_decision.level == PermissionLevel.READ_ONLY
        assert approval_decision.level == PermissionLevel.CONFIRMED_EXECUTION

    def test_dry_run_reports_would_action(self, tmp_path) -> None:
        log_path = tmp_path / "permissions.log"
        middleware = PermissionMiddleware(audit_log_path=log_path, dry_run=True)
        decision = middleware.check(
            PermissionRequest(
                tool_name="shell_exec",
                arguments={"command": "sudo rm -rf /tmp/example"},
            )
        )

        assert decision.action == "allow"
        assert decision.dry_run is True
        assert decision.metadata["would_action"] == "deny"
        assert decision.metadata["would_level"] == "DANGEROUS"

    def test_audit_log_written(self, tmp_path) -> None:
        log_path = tmp_path / "permissions.log"
        middleware = PermissionMiddleware(audit_log_path=log_path)
        middleware.check(
            PermissionRequest(
                tool_name="shell_exec",
                arguments={"command": "echo hello", "secret": "not logged"},
                agent_id="agent-1",
            )
        )

        record = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert record["agent_id"] == "agent-1"
        assert record["tool"] == "shell_exec"
        assert record["action"] == "require_confirmation"
        assert record["argument_keys"] == ["command", "secret"]
        assert record["command_preview"] == "echo hello"

    def test_privacy_mode_blocks_remote_http_request(self, tmp_path) -> None:
        mode_registry = ModeRegistry(state_path=tmp_path / "current_mode.json")
        mode_registry.switch_mode("privacy")
        middleware = PermissionMiddleware(
            audit_log_path=tmp_path / "permissions.log",
            mode_registry=mode_registry,
        )

        decision = middleware.check(
            PermissionRequest(
                tool_name="http_request",
                arguments={"url": "https://example.com", "method": "GET"},
            )
        )

        assert decision.action == "deny"
        assert decision.matched_pattern == "privacy-network-localhost-only"

    def test_privacy_mode_allows_localhost_http_request(self, tmp_path) -> None:
        mode_registry = ModeRegistry(state_path=tmp_path / "current_mode.json")
        mode_registry.switch_mode("privacy")
        middleware = PermissionMiddleware(
            audit_log_path=tmp_path / "permissions.log",
            mode_registry=mode_registry,
        )

        decision = middleware.check(
            PermissionRequest(
                tool_name="http_request",
                arguments={"url": "http://127.0.0.1:11434/api/tags", "method": "GET"},
            )
        )

        assert decision.action == "allow"
        assert decision.level == PermissionLevel.SAFE_ACTION

    def test_privacy_mode_blocks_mcp_adapter(self, tmp_path) -> None:
        mode_registry = ModeRegistry(state_path=tmp_path / "current_mode.json")
        mode_registry.switch_mode("privacy")
        middleware = PermissionMiddleware(
            audit_log_path=tmp_path / "permissions.log",
            mode_registry=mode_registry,
        )

        decision = middleware.check(PermissionRequest(tool_name="mcp_adapter"))

        assert decision.action == "deny"
        assert decision.matched_pattern == "privacy-remote-mcp"

    def test_voice_capture_requires_confirmation(self, tmp_path) -> None:
        middleware = PermissionMiddleware(audit_log_path=tmp_path / "permissions.log")

        decision = middleware.check(
            PermissionRequest(
                tool_name="voice_microphone_capture",
                arguments={"activation": "push_to_talk"},
            )
        )

        assert decision.action == "require_confirmation"
        assert decision.level == PermissionLevel.CONFIRMED_EXECUTION

    def test_privacy_mode_voice_capture_requires_explicit_approval(
        self, tmp_path
    ) -> None:
        mode_registry = ModeRegistry(state_path=tmp_path / "current_mode.json")
        mode_registry.switch_mode("privacy")
        middleware = PermissionMiddleware(
            audit_log_path=tmp_path / "permissions.log",
            mode_registry=mode_registry,
        )

        denied = middleware.check(
            PermissionRequest(tool_name="voice_microphone_capture")
        )
        approved = middleware.check(
            PermissionRequest(
                tool_name="voice_microphone_capture",
                arguments={"explicit_approval": True},
            )
        )

        assert denied.action == "deny"
        assert denied.matched_pattern == "privacy-voice-capture"
        assert approved.action == "require_confirmation"


class _FakeShellTool(BaseTool):
    tool_id = "shell_exec"

    def __init__(self) -> None:
        self.calls = 0

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="shell_exec",
            description="Fake shell.",
            requires_confirmation=True,
        )

    def execute(self, **params: Any) -> ToolResult:
        self.calls += 1
        return ToolResult(
            tool_name="shell_exec",
            content=f"ran {params.get('command', '')}",
            success=True,
        )


class TestToolExecutorPermissionIntegration:
    def test_permission_denial_blocks_before_execute(self, tmp_path) -> None:
        tool = _FakeShellTool()
        executor = ToolExecutor(
            [tool],
            permission_middleware=PermissionMiddleware(
                audit_log_path=tmp_path / "permissions.log"
            ),
        )
        result = executor.execute(
            ToolCall(id="1", name="shell_exec", arguments='{"command":"rm -rf /"}')
        )

        assert result.success is False
        assert "Permission denied" in result.content
        assert tool.calls == 0

    def test_permission_confirmation_uses_single_prompt(self, tmp_path) -> None:
        prompts: list[str] = []
        tool = _FakeShellTool()
        executor = ToolExecutor(
            [tool],
            interactive=True,
            confirm_callback=lambda prompt: prompts.append(prompt) or True,
            permission_middleware=PermissionMiddleware(
                audit_log_path=tmp_path / "permissions.log"
            ),
        )
        result = executor.execute(
            ToolCall(id="1", name="shell_exec", arguments='{"command":"echo hi"}')
        )

        assert result.success is True
        assert result.content == "ran echo hi"
        assert tool.calls == 1
        assert len(prompts) == 1
        assert "shell command requires confirmation" in prompts[0]

    def test_permission_dry_run_does_not_execute(self, tmp_path) -> None:
        tool = _FakeShellTool()
        executor = ToolExecutor(
            [tool],
            permission_middleware=PermissionMiddleware(
                audit_log_path=tmp_path / "permissions.log",
                dry_run=True,
            ),
        )
        result = executor.execute(
            ToolCall(id="1", name="shell_exec", arguments='{"command":"rm -rf /"}')
        )

        assert result.success is True
        assert "Permission dry run" in result.content
        assert result.metadata["permission"]["would_action"] == "deny"
        assert tool.calls == 0
