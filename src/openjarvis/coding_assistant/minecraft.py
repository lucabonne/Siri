"""Minecraft mod stack detection and diagnostics."""

# ruff: noqa: E501

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from openjarvis.coding_assistant.gradle import read_gradle_text
from openjarvis.coding_assistant.models import BuildFailure


def detect_minecraft(root: str | Path) -> dict[str, Any]:
    text = read_gradle_text(root)
    lower = text.lower()
    version = _first(
        text,
        [
            r"""minecraft\s+["']com\.mojang:minecraft:([^"']+)["']""",
            r"""minecraft_version\s*=\s*([^\s]+)""",
            r"""minecraft\s*=\s*["']([^"']+)["']""",
        ],
    )
    return {
        "present": "minecraft" in lower
        or (Path(root) / "src/main/resources/fabric.mod.json").exists(),
        "minecraft_version": version,
        "mapping_version": _first(text, [r"""yarn_mappings\s*=\s*([^\s]+)"""]),
    }


def analyze_minecraft_errors(text: str) -> list[BuildFailure]:
    lower = text.lower()
    failures: list[BuildFailure] = []
    if (
        "decompile" in lower
        and "failed" in lower
        or "remap" in lower
        and "failed" in lower
    ):
        failures.append(
            BuildFailure(
                category="minecraft_mapping_or_remap",
                severity="error",
                summary="Minecraft remap/decompile tooling failed.",
                evidence=_evidence(text, ["decompile", "remap", "failed"]),
                likely_causes=[
                    "Loom cache, Minecraft version, or mapping version is inconsistent.",
                    "A dependency targets a different Minecraft version.",
                ],
                safe_fixes=[
                    "Confirm Minecraft, Yarn mappings, Loom, and Fabric API versions as a set.",
                    "Clear Loom caches only after preserving current diagnostics.",
                ],
                related_stack=["Minecraft Mod", "Loom"],
            )
        )
    if "client-only" in lower or "dedicated server" in lower:
        failures.append(
            BuildFailure(
                category="minecraft_environment_split",
                severity="error",
                summary="Client/server environment-specific code may be loaded in the wrong runtime.",
                evidence=_evidence(text, ["client-only", "dedicated server"]),
                likely_causes=[
                    "Client classes are referenced from common or server entrypoints.",
                    "Environment annotations or source-set separation may be incomplete.",
                ],
                safe_fixes=[
                    "Trace the referenced class from the first stack frame in mod code.",
                    "Keep client-only registration behind Fabric client entrypoints.",
                ],
                related_stack=["Minecraft Mod", "Fabric"],
            )
        )
    return failures


def _first(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _evidence(text: str, needles: list[str]) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if any(needle.lower() in line.lower() for needle in needles)
    ][:5]


__all__ = ["analyze_minecraft_errors", "detect_minecraft"]
