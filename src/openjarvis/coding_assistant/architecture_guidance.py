"""Repo-aware architecture explanations for coding assistance."""

# ruff: noqa: E501

from __future__ import annotations

from openjarvis.coding_assistant.models import (
    ArchitectureExplanation,
    CodingStackProfile,
)
from openjarvis.repo_index.models import RepoSummary


def explain_architecture(
    summary: RepoSummary,
    stack: CodingStackProfile,
    *,
    privacy_mode: bool = False,
) -> ArchitectureExplanation:
    architecture = summary.architecture
    graph = summary.dependency_graph
    systems = []
    for module in architecture.modules[:8]:
        systems.append(
            {
                "name": module.get("name", ""),
                "file_count": module.get("file_count", 0),
                "languages": module.get("languages", {}),
                "notable_files": module.get("notable_files", []),
            }
        )
    summary_text = _summary_text(summary, stack)
    debugging_entry_points = list(
        dict.fromkeys(architecture.entry_points + architecture.build_files)
    )[:12]
    return ArchitectureExplanation(
        summary=summary_text,
        entry_points=architecture.entry_points[:20],
        major_systems=systems,
        dependencies=graph.direct_dependencies[:24],
        risky_refactors=risky_refactors(summary, stack),
        debugging_entry_points=debugging_entry_points,
        privacy_mode=privacy_mode,
    )


def risky_refactors(summary: RepoSummary, stack: CodingStackProfile) -> list[str]:
    risks: list[str] = []
    labels = set(stack.specializations + stack.frameworks + stack.build_systems)
    if "Minecraft Mod" in labels:
        risks.append(
            "Moving Java packages can break Fabric entrypoint and mixin metadata."
        )
    if "Loom" in labels or "Gradle" in labels:
        risks.append(
            "Changing Gradle source sets, mappings, or dependency scopes can affect generated Minecraft build tasks."
        )
    if "Vite" in labels:
        risks.append(
            "Renaming frontend entry files can break Vite config, import aliases, or Tauri integration."
        )
    if "Rust" in labels:
        risks.append(
            "Moving Rust modules can break `mod` declarations and crate workspace paths."
        )
    if "Python" in labels:
        risks.append(
            "Renaming Python packages can break imports, console entry points, and test discovery."
        )
    if summary.dependency_graph.internal_edges:
        risks.append(
            "High-fanout modules should be refactored behind compatibility shims or in small steps."
        )
    return list(dict.fromkeys(risks))[:8]


def _summary_text(summary: RepoSummary, stack: CodingStackProfile) -> str:
    project = stack.project_type or summary.detected_stack.project_type
    languages = ", ".join(stack.languages[:4]) or "unknown languages"
    modules = ", ".join(
        str(module.get("name", ""))
        for module in summary.architecture.modules[:4]
        if module.get("name")
    )
    if modules:
        return f"This {project} is primarily {languages}, organized around {modules}."
    return f"This {project} is primarily {languages} with {summary.indexed_file_count} indexed files."


__all__ = ["explain_architecture", "risky_refactors"]
