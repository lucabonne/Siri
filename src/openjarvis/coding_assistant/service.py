"""Passive coding assistant service.

This layer composes repository indexing, terminal context, memory snapshots,
agent workspace metadata, and permission dry-runs. It never edits files,
executes commands, or uploads repository content.
"""

# ruff: noqa: E501

from __future__ import annotations

from pathlib import Path
from typing import Any

from openjarvis.coding_assistant.architecture_guidance import explain_architecture
from openjarvis.coding_assistant.build_analysis import analyze_build_output
from openjarvis.coding_assistant.debugging import debugging_steps_for
from openjarvis.coding_assistant.fabric import detect_fabric
from openjarvis.coding_assistant.gradle import detect_gradle
from openjarvis.coding_assistant.java import detect_java
from openjarvis.coding_assistant.minecraft import detect_minecraft
from openjarvis.coding_assistant.models import (
    BuildAnalysis,
    CodingPanelSnapshot,
    CodingStackProfile,
    DebuggingSummary,
    ProjectHealthSummary,
    SafeFixSuggestion,
)
from openjarvis.coding_assistant.refactor_guidance import risky_refactor_guidance
from openjarvis.context.terminal import TerminalContextStore
from openjarvis.repo_index import RepoIndexService
from openjarvis.repo_index.models import RepoSummary
from openjarvis.security.permissions import PermissionMiddleware


class CodingAssistantService:
    """Read-only local developer intelligence service."""

    def __init__(
        self,
        *,
        repo_index_service: RepoIndexService | None = None,
        terminal_store: TerminalContextStore | None = None,
        memory_service: Any | None = None,
        permission_middleware: PermissionMiddleware | None = None,
        agent_workspace_registry: Any | None = None,
    ) -> None:
        self.repo_index_service = repo_index_service or RepoIndexService(
            memory_service=memory_service
        )
        self.terminal_store = terminal_store or TerminalContextStore()
        self.memory_service = memory_service
        self.permission_middleware = permission_middleware or PermissionMiddleware()
        self.agent_workspace_registry = agent_workspace_registry

    def detect_stack(
        self,
        cwd: str | Path | None = None,
        *,
        privacy_mode: bool = False,
    ) -> CodingStackProfile:
        summary = self.repo_index_service.repo_summary(cwd, privacy_mode=privacy_mode)
        return self._stack_profile(summary)

    def analyze_build(
        self,
        cwd: str | Path | None = None,
        *,
        command: str = "",
        output: str = "",
        exit_code: int | None = None,
        privacy_mode: bool = False,
    ) -> BuildAnalysis:
        root = self._root_for(cwd, privacy_mode=privacy_mode)
        return analyze_build_output(
            cwd=root,
            command=command,
            output=output,
            exit_code=exit_code,
            privacy_mode=privacy_mode,
            permission_middleware=self.permission_middleware,
        )

    def explain_architecture(
        self,
        cwd: str | Path | None = None,
        *,
        privacy_mode: bool = False,
    ):
        summary = self.repo_index_service.repo_summary(cwd, privacy_mode=privacy_mode)
        return explain_architecture(
            summary,
            self._stack_profile(summary),
            privacy_mode=privacy_mode,
        )

    def repo_debugging_summary(
        self,
        cwd: str | Path | None = None,
        *,
        privacy_mode: bool = False,
    ) -> DebuggingSummary:
        summary = self.repo_index_service.repo_summary(cwd, privacy_mode=privacy_mode)
        stack = self._stack_profile(summary)
        terminal = self.terminal_store.current_context(
            cwd=summary.root,
            privacy_mode=privacy_mode,
        )
        current = terminal.current
        build = analyze_build_output(
            cwd=summary.root,
            command=current.command if current else "",
            output=current.output if current else "",
            exit_code=current.exit_code if current else None,
            privacy_mode=privacy_mode,
            permission_middleware=self.permission_middleware,
        )
        labels = stack.frameworks + stack.build_systems + stack.specializations
        related = _related_files(summary, build.failures)
        if build.failures:
            text = (
                f"Recent terminal/build output indicates {build.failures[0].category}."
            )
        else:
            text = "No recent coding failure is captured; use architecture entry points for manual debugging."
        return DebuggingSummary(
            summary=text,
            recent_errors=build.failures,
            debugging_steps=debugging_steps_for(build.failures, labels),
            related_files=related,
            terminal_context=terminal.to_dict(),
            privacy_mode=privacy_mode,
        )

    def safe_fix_suggestions(
        self,
        cwd: str | Path | None = None,
        *,
        command: str = "",
        output: str = "",
        exit_code: int | None = None,
        privacy_mode: bool = False,
    ) -> list[SafeFixSuggestion]:
        return self.analyze_build(
            cwd,
            command=command,
            output=output,
            exit_code=exit_code,
            privacy_mode=privacy_mode,
        ).suggested_fixes

    def project_health_summary(
        self,
        cwd: str | Path | None = None,
        *,
        privacy_mode: bool = False,
        persist_memory: bool = False,
    ) -> ProjectHealthSummary:
        summary = self.repo_index_service.index_repository(
            cwd,
            privacy_mode=privacy_mode,
            persist_memory=persist_memory and not privacy_mode,
        )
        stack = self._stack_profile(summary)
        strengths: list[str] = []
        concerns: list[str] = []
        next_steps: list[str] = []

        if summary.architecture.entry_points:
            strengths.append("Entry points detected")
        else:
            concerns.append("No clear entry point detected")
        if summary.architecture.build_files:
            strengths.append("Build/config files detected")
        else:
            concerns.append("No build file detected")
        if summary.architecture.metadata.get("has_tests"):
            strengths.append("Tests are present")
        else:
            concerns.append("No tests detected by the index")
        if stack.specializations:
            strengths.append(
                f"Specialized stack detected: {', '.join(stack.specializations[:4])}"
            )
        if (
            stack.java_version
            and stack.java_version != "21"
            and "Minecraft Mod" in stack.specializations
        ):
            concerns.append(
                "Minecraft/Fabric projects commonly need aligned Java toolchains"
            )
        next_steps.extend(
            risky_refactor_guidance(
                stack.specializations + stack.frameworks + stack.build_systems
            )
        )
        score = max(20, min(100, 80 + len(strengths) * 4 - len(concerns) * 10))
        status = (
            "healthy" if score >= 75 else "watch" if score >= 50 else "needs_attention"
        )
        return ProjectHealthSummary(
            status=status,
            score=score,
            strengths=strengths,
            concerns=concerns,
            next_steps=next_steps[:8],
            stack=stack,
            privacy_mode=privacy_mode,
        )

    def coding_panel(
        self,
        cwd: str | Path | None = None,
        *,
        privacy_mode: bool = False,
    ) -> CodingPanelSnapshot:
        summary = self.repo_index_service.repo_summary(cwd, privacy_mode=privacy_mode)
        stack = self._stack_profile(summary)
        debug = self.repo_debugging_summary(summary.root, privacy_mode=privacy_mode)
        build = analyze_build_output(
            cwd=summary.root,
            command=str(debug.terminal_context.get("current", {}).get("command", ""))
            if debug.terminal_context.get("current")
            else "",
            output=str(debug.terminal_context.get("current", {}).get("output", ""))
            if debug.terminal_context.get("current")
            else "",
            exit_code=debug.terminal_context.get("current", {}).get("exit_code")
            if debug.terminal_context.get("current")
            else None,
            privacy_mode=privacy_mode,
            permission_middleware=self.permission_middleware,
        )
        health = self.project_health_summary(summary.root, privacy_mode=privacy_mode)
        return CodingPanelSnapshot(
            build_health=build,
            repo_health=health,
            current_stack=stack,
            recent_errors=debug.recent_errors,
            suggested_fixes=build.suggested_fixes,
            architecture_overview=explain_architecture(
                summary, stack, privacy_mode=privacy_mode
            ),
            active_agent=self._active_agent_metadata(),
            privacy_mode=privacy_mode,
        )

    def _stack_profile(self, summary: RepoSummary) -> CodingStackProfile:
        root = summary.root
        base = summary.detected_stack
        gradle = detect_gradle(root)
        fabric = detect_fabric(root)
        minecraft = detect_minecraft(root)
        java = detect_java(root)
        specializations: list[str] = []
        if gradle.get("present"):
            specializations.append("Gradle")
        if gradle.get("uses_fabric_loom"):
            specializations.append("Loom")
        if fabric.get("present"):
            specializations.append("Fabric")
        if minecraft.get("present"):
            specializations.append("Minecraft Mod")
        if java.get("java_21"):
            specializations.append("Java 21")
        if any(
            label in base.frameworks for label in ("Vite", "React", "Vue", "Next.js")
        ):
            specializations.append("Node/Vite")
        if "Rust" in base.frameworks or "Cargo" in base.build_systems:
            specializations.append("Rust")
        if "Python" in base.frameworks or "Python" in base.languages:
            specializations.append("Python")
        return CodingStackProfile(
            languages=base.languages,
            frameworks=base.frameworks,
            build_systems=base.build_systems,
            package_managers=base.package_managers,
            specializations=list(dict.fromkeys(specializations)),
            project_type=base.project_type,
            java_version=str(java.get("version") or ""),
            minecraft_version=str(minecraft.get("minecraft_version") or ""),
            loom_version=str(gradle.get("version") or ""),
            node_package_manager=_node_manager(summary),
            vite_present="Vite" in base.frameworks,
            rust_workspace="Cargo" in base.build_systems,
            python_project="Python" in base.frameworks or "Python" in base.languages,
        )

    def _root_for(self, cwd: str | Path | None, *, privacy_mode: bool) -> str:
        return self.repo_index_service.repo_summary(cwd, privacy_mode=privacy_mode).root

    def _active_agent_metadata(self) -> dict[str, Any]:
        registry = self.agent_workspace_registry
        if registry is None:
            return {}
        try:
            active = registry.get_active_agent()
            return {
                "id": active.id,
                "display_name": active.display_name,
                "permission_ceiling": getattr(
                    active.permission_ceiling, "name", active.permission_ceiling
                ),
                "memory_scope": list(active.memory_scope),
            }
        except Exception:
            return {}


def _node_manager(summary: RepoSummary) -> str:
    managers = set(summary.detected_stack.package_managers)
    for name in ("pnpm", "Yarn", "npm"):
        if name in managers:
            return name
    return ""


def _related_files(summary: RepoSummary, failures: list[Any]) -> list[str]:
    text = "\n".join(
        "\n".join(failure.evidence) + " " + failure.summary for failure in failures
    )
    related = [
        file.path
        for file in summary.file_summaries
        if file.path in text
        or any(symbol and symbol in text for symbol in file.symbols)
    ]
    if related:
        return related[:10]
    return summary.architecture.entry_points[:10]


def get_coding_assistant_service(**kwargs: Any) -> CodingAssistantService:
    return CodingAssistantService(**kwargs)


__all__ = ["CodingAssistantService", "get_coding_assistant_service"]
