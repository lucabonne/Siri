"""Build analysis orchestration for the passive coding assistant."""

# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path

from openjarvis.coding_assistant.debugging import parse_build_errors
from openjarvis.coding_assistant.gradle import gradle_safe_commands
from openjarvis.coding_assistant.models import BuildAnalysis, SafeFixSuggestion
from openjarvis.coding_assistant.refactor_guidance import safe_fix_suggestions
from openjarvis.security.permissions import PermissionMiddleware, PermissionRequest


def analyze_build_output(
    *,
    cwd: str | Path,
    command: str = "",
    output: str = "",
    exit_code: int | None = None,
    privacy_mode: bool = False,
    permission_middleware: PermissionMiddleware | None = None,
) -> BuildAnalysis:
    failures = parse_build_errors(output, command=command, exit_code=exit_code)
    has_failure = bool(failures) or exit_code not in (None, 0)
    suggestions = safe_fix_suggestions(failures)
    suggestions.extend(_diagnostic_command_suggestions(cwd, permission_middleware))
    if privacy_mode and has_failure:
        summary = "Build failure detected while Privacy Mode is active; analysis stayed local."
    elif has_failure:
        categories = (
            ", ".join(failure.category for failure in failures[:4]) or "nonzero_exit"
        )
        summary = f"Detected build failure categories: {categories}."
    elif command or output:
        summary = "No specialized build failure was detected."
    else:
        summary = "No build output has been provided yet."
    return BuildAnalysis(
        has_failure=has_failure,
        status="failing" if has_failure else "clear",
        command=command,
        exit_code=exit_code,
        summary=summary,
        failures=failures,
        suggested_fixes=suggestions[:10],
        privacy_mode=privacy_mode,
    )


def _diagnostic_command_suggestions(
    cwd: str | Path,
    permission_middleware: PermissionMiddleware | None,
) -> list[SafeFixSuggestion]:
    root = Path(cwd)
    commands: list[tuple[str, str]] = []
    if any(
        (root / rel).exists()
        for rel in (
            "build.gradle",
            "build.gradle.kts",
            "settings.gradle",
            "settings.gradle.kts",
        )
    ):
        commands.extend(gradle_safe_commands(root))
    if (root / "package.json").exists() or (root / "frontend/package.json").exists():
        commands.append(
            ("npm run", "List available package scripts without running a build.")
        )
    if (root / "Cargo.toml").exists() or (root / "rust/Cargo.toml").exists():
        commands.append(
            (
                "cargo metadata --no-deps",
                "Inspect Rust workspace metadata without compiling.",
            )
        )
    if (root / "pyproject.toml").exists():
        commands.append(
            (
                "python -m pytest --collect-only -q",
                "Collect Python tests without running them.",
            )
        )

    middleware = permission_middleware or PermissionMiddleware()
    suggestions: list[SafeFixSuggestion] = []
    for command, rationale in commands[:4]:
        decision = middleware.check(
            PermissionRequest(
                tool_name="shell_exec",
                command=command,
                arguments={"command": command},
                dry_run=True,
                metadata={"source": "coding_assistant", "passive_only": True},
            )
        )
        suggestions.append(
            SafeFixSuggestion(
                title="Diagnostic command",
                rationale=rationale,
                steps=["Review and approve explicitly before running."],
                risk="low",
                command=command,
                permission_preview={
                    "would_action": decision.metadata.get(
                        "would_action", decision.action
                    ),
                    "would_level": decision.metadata.get(
                        "would_level", decision.level.name
                    ),
                    "reason": decision.reason,
                    "matched_pattern": decision.matched_pattern,
                },
            )
        )
    return suggestions


__all__ = ["analyze_build_output"]
