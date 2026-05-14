"""Passive terminal context capture and local error analysis."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from openjarvis.context.layer import ContextLayer
from openjarvis.security.permissions import (
    PermissionLevel,
    PermissionMiddleware,
    PermissionRequest,
)

_MAX_OUTPUT_CHARS = 12000
_MAX_PREVIEW_CHARS = 1200
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|bearer)\s*[:=]\s*\S+"),
    re.compile(
        r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", re.S
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _shell_type(shell: str | None = None) -> str:
    raw = shell or os.environ.get("SHELL", "")
    return Path(raw).name if raw else ""


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3]}..."


def _sanitize(text: str) -> str:
    cleaned = text
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[redacted secret]", cleaned)
    return cleaned


def _redacted_record(record: "TerminalCommandRecord") -> "TerminalCommandRecord":
    data = record.to_dict()
    data["command"] = "[redacted terminal command]"
    data["output"] = "[redacted terminal output]" if record.output else ""
    data["output_preview"] = (
        "[redacted terminal output]" if record.output_preview else ""
    )
    return TerminalCommandRecord.from_dict(data)


@dataclass(slots=True)
class SuggestedTerminalCommand:
    """A non-executing command suggestion annotated by the permission layer."""

    id: str
    command: str
    reason: str
    safety: str
    permission_level: str
    permission_action: str
    requires_approval: bool
    dangerous: bool = False
    matched_pattern: str | None = None
    dry_run_preview: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TerminalErrorAnalysis:
    """Lightweight local analysis for the most recent terminal failure."""

    has_error: bool = False
    summary: str = ""
    patterns: list[str] = field(default_factory=list)
    possible_fixes: list[str] = field(default_factory=list)
    suggested_commands: list[SuggestedTerminalCommand] = field(default_factory=list)
    local_only: bool = True
    passive_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["suggested_commands"] = [
            command.to_dict() for command in self.suggested_commands
        ]
        return data


@dataclass(slots=True)
class TerminalCommandRecord:
    """A passive snapshot of a completed terminal command."""

    command: str
    output: str = ""
    exit_code: int | None = None
    cwd: str = ""
    repo_context: dict[str, Any] = field(default_factory=dict)
    shell_type: str = ""
    timestamp: str = field(default_factory=_now)
    output_preview: str = ""
    passive_only: bool = True
    local_only: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TerminalCommandRecord":
        output = str(data.get("output", ""))
        return cls(
            command=str(data.get("command", "")),
            output=output,
            exit_code=(
                int(data["exit_code"]) if data.get("exit_code") is not None else None
            ),
            cwd=str(data.get("cwd", "")),
            repo_context=dict(data.get("repo_context") or {}),
            shell_type=str(data.get("shell_type", "")),
            timestamp=str(data.get("timestamp") or _now()),
            output_preview=str(
                data.get("output_preview") or _truncate(output, _MAX_PREVIEW_CHARS)
            ),
            passive_only=bool(data.get("passive_only", True)),
            local_only=bool(data.get("local_only", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TerminalContextSnapshot:
    """Current terminal context plus recent history and local analysis."""

    current: TerminalCommandRecord | None = None
    history: list[TerminalCommandRecord] = field(default_factory=list)
    error_summary: TerminalErrorAnalysis = field(default_factory=TerminalErrorAnalysis)
    cwd: str = ""
    shell_type: str = ""
    project_context: dict[str, Any] = field(default_factory=dict)
    privacy_mode: bool = False
    passive_only: bool = True
    local_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "current": self.current.to_dict() if self.current else None,
            "history": [record.to_dict() for record in self.history],
            "error_summary": self.error_summary.to_dict(),
            "cwd": self.cwd,
            "shell_type": self.shell_type,
            "project_context": self.project_context,
            "privacy_mode": self.privacy_mode,
            "passive_only": self.passive_only,
            "local_only": self.local_only,
        }


class TerminalErrorAnalyzer:
    """Rule-based, local-only terminal error analyzer."""

    def __init__(
        self, permission_middleware: PermissionMiddleware | None = None
    ) -> None:
        self._permissions = permission_middleware or PermissionMiddleware()

    def analyze(
        self,
        record: TerminalCommandRecord | None,
        *,
        dry_run: bool = True,
    ) -> TerminalErrorAnalysis:
        if record is None:
            return TerminalErrorAnalysis(
                summary="No terminal command has been captured yet."
            )

        combined = f"{record.command}\n{record.output}"
        if record.exit_code in (None, 0) and not self._looks_error_like(combined):
            return TerminalErrorAnalysis(
                has_error=False,
                summary="Last command completed without a detected terminal error.",
                possible_fixes=["No fix needed from the last captured command."],
            )

        patterns: list[str] = []
        fixes: list[str] = []
        commands: list[tuple[str, str, str]] = []

        lower = combined.lower()
        if (
            re.search(r"\b(module|modulenotfounderror|importerror):", lower)
            or "cannot find module" in lower
        ):
            patterns.append("missing_dependency")
            package = _extract_missing_package(combined)
            fixes.append(
                "A dependency appears to be missing or unavailable in this environment."
            )
            if package:
                commands.append(
                    (
                        f"python -m pip install {package}",
                        f"Install missing Python package '{package}'.",
                        "dependency",
                    )
                )
            commands.append(
                (
                    "python -m pip install -r requirements.txt",
                    "Install declared Python dependencies.",
                    "dependency",
                )
            )

        if "command not found" in lower or "not recognized as an internal" in lower:
            patterns.append("command_not_found")
            missing = _extract_command_not_found(combined)
            fixes.append("The shell could not find an executable on PATH.")
            if missing:
                commands.append(
                    (
                        f"which {missing}",
                        f"Check whether '{missing}' is installed and on PATH.",
                        "diagnostic",
                    )
                )

        if "permission denied" in lower or "operation not permitted" in lower:
            patterns.append("permission_denied")
            fixes.append("The command hit a filesystem or OS permission boundary.")
            commands.append(
                (
                    "ls -la",
                    "Inspect permissions in the current directory.",
                    "diagnostic",
                )
            )

        if "eaddrinuse" in lower or "address already in use" in lower:
            patterns.append("port_in_use")
            port = _extract_port(combined)
            fixes.append("A server port is already occupied by another process.")
            if port:
                commands.append(
                    (
                        f"lsof -i :{port}",
                        f"Find the process using port {port}.",
                        "diagnostic",
                    )
                )

        if "merge conflict" in lower or "unmerged paths" in lower:
            patterns.append("git_conflict")
            fixes.append("The repository has unresolved merge conflicts.")
            commands.extend(
                [
                    (
                        "git status --short",
                        "List conflicted and changed files.",
                        "diagnostic",
                    ),
                    (
                        "git diff --check",
                        "Check for conflict markers and whitespace errors.",
                        "diagnostic",
                    ),
                ]
            )

        if "syntaxerror" in lower:
            patterns.append("syntax_error")
            fixes.append(
                "A parser rejected the source; inspect the referenced file and line."
            )

        if "traceback (most recent call last)" in lower:
            patterns.append("python_traceback")
            fixes.append(
                "A Python exception traceback was emitted; start from the final "
                "exception line."
            )
            commands.append(
                (
                    "python -m pytest -q",
                    "Rerun Python tests with concise output.",
                    "diagnostic",
                )
            )

        if re.search(r"\bts\d{4}\b", combined, flags=re.IGNORECASE):
            patterns.append("typescript_error")
            fixes.append("TypeScript reported one or more compile errors.")
            commands.append(
                ("npm run typecheck", "Rerun the TypeScript checker.", "diagnostic")
            )

        if re.search(r"\berror\[E\d{4}\]", combined):
            patterns.append("rust_error")
            fixes.append("Rust compiler diagnostics were detected.")
            commands.append(
                (
                    "cargo check",
                    "Rerun Rust compiler checks without building artifacts.",
                    "diagnostic",
                )
            )

        if not patterns:
            patterns.append("generic_nonzero_exit")
            fixes.append(
                "The command exited non-zero. Review the last error lines and rerun "
                "the smallest diagnostic command."
            )

        commands.insert(
            0, (record.command, "Rerun the last command after applying a fix.", "rerun")
        )
        suggested = self._suggested_commands(commands, dry_run=dry_run)
        return TerminalErrorAnalysis(
            has_error=True,
            summary=self._summary(record, patterns),
            patterns=_dedupe(patterns),
            possible_fixes=_dedupe(fixes),
            suggested_commands=suggested,
        )

    @staticmethod
    def _looks_error_like(text: str) -> bool:
        lower = text.lower()
        return any(
            token in lower
            for token in (
                "error:",
                "traceback",
                "exception",
                "failed",
                "permission denied",
                "command not found",
            )
        )

    @staticmethod
    def _summary(record: TerminalCommandRecord, patterns: list[str]) -> str:
        pattern_text = ", ".join(_dedupe(patterns))
        exit_text = "unknown" if record.exit_code is None else str(record.exit_code)
        return (
            f"`{record.command}` exited with code {exit_text}; detected {pattern_text}."
        )

    def _suggested_commands(
        self,
        commands: Iterable[tuple[str, str, str]],
        *,
        dry_run: bool,
    ) -> list[SuggestedTerminalCommand]:
        suggestions: list[SuggestedTerminalCommand] = []
        seen: set[str] = set()
        for command, reason, safety in commands:
            command = command.strip()
            if not command or command in seen:
                continue
            seen.add(command)
            request = PermissionRequest(
                tool_name="shell_exec",
                command=command,
                arguments={"command": command},
                dry_run=dry_run,
                metadata={"source": "terminal_copilot", "passive_only": True},
            )
            decision = self._permissions.check(request)
            level = decision.metadata.get("would_level") or decision.level.name
            action = decision.metadata.get("would_action") or decision.action
            dangerous = level == PermissionLevel.DANGEROUS.name
            suggestions.append(
                SuggestedTerminalCommand(
                    id=_command_id(command),
                    command=command,
                    reason=reason,
                    safety="dangerous" if dangerous else safety,
                    permission_level=str(level),
                    permission_action=str(action),
                    requires_approval=level
                    in {
                        PermissionLevel.CONFIRMED_EXECUTION.name,
                        PermissionLevel.DANGEROUS.name,
                    },
                    dangerous=dangerous,
                    matched_pattern=decision.matched_pattern,
                    dry_run_preview={
                        "enabled": dry_run,
                        "would_action": action,
                        "would_level": level,
                        "reason": decision.reason,
                    },
                )
            )
        return suggestions[:6]


class TerminalContextStore:
    """File-backed passive terminal history store."""

    def __init__(
        self,
        history_path: str | Path | None = None,
        *,
        max_history: int = 100,
        permission_middleware: PermissionMiddleware | None = None,
    ) -> None:
        default_path = Path.home() / ".openjarvis" / "terminal_history.jsonl"
        self.history_path = Path(history_path or default_path).expanduser()
        self.max_history = max_history
        self._analyzer = TerminalErrorAnalyzer(permission_middleware)

    def record(
        self,
        *,
        command: str,
        output: str = "",
        exit_code: int | None = None,
        cwd: str | os.PathLike[str] | None = None,
        shell_type: str | None = None,
        timestamp: str | None = None,
    ) -> TerminalCommandRecord:
        cwd_path = Path(cwd or os.getcwd()).expanduser()
        layer = ContextLayer(cwd=cwd_path)
        project = layer.current_project_context()
        sanitized_output = _truncate(_sanitize(output), _MAX_OUTPUT_CHARS)
        record = TerminalCommandRecord(
            command=_sanitize(command.strip()),
            output=sanitized_output,
            exit_code=exit_code,
            cwd=str(cwd_path),
            repo_context={
                "git_repository": project.git_repository,
                "current_branch": project.current_branch,
                "project_type": project.project_type,
                "languages": project.languages,
                "package_manager": project.package_manager,
                "framework_build_system": project.framework_build_system,
            },
            shell_type=_shell_type(shell_type),
            timestamp=timestamp or _now(),
            output_preview=_truncate(sanitized_output, _MAX_PREVIEW_CHARS),
        )
        self._append(record)
        return record

    def current_context(
        self,
        *,
        cwd: str | os.PathLike[str] | None = None,
        privacy_mode: bool = False,
        limit: int = 10,
    ) -> TerminalContextSnapshot:
        history = self.recent_history(limit=limit, privacy_mode=privacy_mode)
        current = history[0] if history else None
        cwd_path = Path(cwd or (current.cwd if current else os.getcwd())).expanduser()
        project = ContextLayer(cwd=cwd_path).current_project_context().to_dict()
        analysis_record = (
            None
            if current is None
            else (
                self._raw_recent(1)[0]
                if privacy_mode and self._raw_recent(1)
                else current
            )
        )
        analysis = self._analyzer.analyze(analysis_record, dry_run=True)
        if privacy_mode and analysis.has_error:
            analysis.summary = (
                "Terminal error detected while Privacy Mode is active; raw command "
                "output is redacted."
            )
        return TerminalContextSnapshot(
            current=current,
            history=history,
            error_summary=analysis,
            cwd=str(cwd_path),
            shell_type=current.shell_type if current else _shell_type(),
            project_context=project,
            privacy_mode=privacy_mode,
        )

    def recent_history(
        self,
        *,
        limit: int = 20,
        privacy_mode: bool = False,
    ) -> list[TerminalCommandRecord]:
        records = self._raw_recent(limit)
        if privacy_mode:
            return [_redacted_record(record) for record in records]
        return records

    def error_summary(self, *, privacy_mode: bool = False) -> TerminalErrorAnalysis:
        current = self._raw_recent(1)
        analysis = self._analyzer.analyze(current[0] if current else None, dry_run=True)
        if privacy_mode and analysis.has_error:
            analysis.summary = (
                "Terminal error detected while Privacy Mode is active; raw command "
                "output is redacted."
            )
        return analysis

    def suggested_fixes(self, *, privacy_mode: bool = False) -> dict[str, Any]:
        analysis = self.error_summary(privacy_mode=privacy_mode)
        return {
            "summary": analysis.summary,
            "patterns": analysis.patterns,
            "possible_fixes": analysis.possible_fixes,
            "suggested_commands": [
                command.to_dict() for command in analysis.suggested_commands
            ],
            "passive_only": True,
            "local_only": True,
        }

    def find_suggested_command(
        self, command_id: str
    ) -> SuggestedTerminalCommand | None:
        for command in self.error_summary().suggested_commands:
            if command.id == command_id:
                return command
        return None

    def _append(self, record: TerminalCommandRecord) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read_all()
        existing.append(record)
        existing = existing[-self.max_history :]
        with self.history_path.open("w", encoding="utf-8") as fh:
            for item in existing:
                fh.write(json.dumps(item.to_dict(), sort_keys=True) + "\n")

    def _raw_recent(self, limit: int = 20) -> list[TerminalCommandRecord]:
        records = self._read_all()
        records.sort(key=lambda record: record.timestamp, reverse=True)
        return records[: max(0, min(limit, self.max_history))]

    def _read_all(self) -> list[TerminalCommandRecord]:
        if not self.history_path.exists():
            return []
        records: list[TerminalCommandRecord] = []
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            try:
                records.append(TerminalCommandRecord.from_dict(json.loads(line)))
            except Exception:
                continue
        return records


def _command_id(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8")).hexdigest()[:16]


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            result.append(value)
            seen.add(value)
    return result


def _extract_missing_package(text: str) -> str:
    patterns = (
        r"No module named ['\"]([^'\"]+)['\"]",
        r"Cannot find module ['\"]([^'\"]+)['\"]",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return re.sub(r"[^A-Za-z0-9_.-]", "", match.group(1).split(".")[0])
    return ""


def _extract_command_not_found(text: str) -> str:
    patterns = (
        r"([A-Za-z0-9_.-]+): command not found",
        r"command not found: ([A-Za-z0-9_.-]+)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _extract_port(text: str) -> str:
    match = re.search(r"(?:port|:)\s*(\d{2,5})", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""


__all__ = [
    "SuggestedTerminalCommand",
    "TerminalCommandRecord",
    "TerminalContextSnapshot",
    "TerminalContextStore",
    "TerminalErrorAnalysis",
    "TerminalErrorAnalyzer",
]
