from __future__ import annotations

from pathlib import Path

from openjarvis.context.terminal import TerminalContextStore, TerminalErrorAnalyzer
from openjarvis.memory import MemoryService
from openjarvis.security.permissions import PermissionLevel, PermissionMiddleware


def test_terminal_store_captures_command_context_and_history(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["fastapi>=0.110"]\n',
        encoding="utf-8",
    )
    store = TerminalContextStore(history_path=tmp_path / "terminal.jsonl")

    record = store.record(
        command="python app.py",
        output=(
            "Traceback (most recent call last):\n"
            "ModuleNotFoundError: No module named 'rich'\n"
        ),
        exit_code=1,
        cwd=tmp_path,
        shell_type="zsh",
        timestamp="2026-05-14T10:00:00+00:00",
    )
    snapshot = store.current_context(cwd=tmp_path)

    assert record.command == "python app.py"
    assert record.exit_code == 1
    assert record.cwd == str(tmp_path)
    assert record.shell_type == "zsh"
    assert record.repo_context["project_type"] in {
        "api/backend service",
        "python",
        "unknown",
    }
    assert snapshot.current is not None
    assert snapshot.current.command == "python app.py"
    assert snapshot.error_summary.has_error is True
    assert "missing_dependency" in snapshot.error_summary.patterns
    assert any(
        "pip install rich" in item.command
        for item in snapshot.error_summary.suggested_commands
    )


def test_terminal_privacy_mode_redacts_command_and_output(tmp_path: Path) -> None:
    store = TerminalContextStore(history_path=tmp_path / "terminal.jsonl")
    store.record(
        command="deploy --token super-secret",
        output="password=12345\npermission denied\n",
        exit_code=1,
        cwd=tmp_path,
    )

    snapshot = store.current_context(cwd=tmp_path, privacy_mode=True)

    assert snapshot.current is not None
    assert snapshot.current.command == "[redacted terminal command]"
    assert snapshot.current.output_preview == "[redacted terminal output]"
    assert snapshot.privacy_mode is True
    assert "Privacy Mode" in snapshot.error_summary.summary


def test_terminal_analyzer_marks_dangerous_suggestions_with_permission_metadata() -> (
    None
):
    analyzer = TerminalErrorAnalyzer(PermissionMiddleware())
    suggestions = analyzer._suggested_commands(
        [("git reset --hard", "Discard local changes.", "dangerous")],
        dry_run=True,
    )

    assert suggestions[0].dangerous is True
    assert suggestions[0].permission_level == PermissionLevel.DANGEROUS.name
    assert suggestions[0].requires_approval is True
    assert suggestions[0].dry_run_preview["would_action"] == "deny"


def test_memory_service_records_terminal_command_history(tmp_path: Path) -> None:
    service = MemoryService(db_path=tmp_path / "memory.db", enable_semantic=False)
    try:
        record = service.record_command_history(
            command="pytest -q",
            cwd=str(tmp_path),
            exit_code=1,
            output_preview="FAILED tests/test_app.py",
            metadata={"source": "terminal_copilot"},
        )
        history = service.list_command_history()
    finally:
        service.close()

    assert record["command"] == "pytest -q"
    assert history[0]["output_preview"] == "FAILED tests/test_app.py"
    assert history[0]["metadata"]["source"] == "terminal_copilot"
