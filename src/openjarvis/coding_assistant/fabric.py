"""Fabric mod passive detection and diagnostics."""

# ruff: noqa: E501

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openjarvis.coding_assistant.gradle import read_gradle_text
from openjarvis.coding_assistant.models import BuildFailure


def detect_fabric(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    gradle_text = read_gradle_text(root_path)
    metadata = _read_json(root_path / "src/main/resources/fabric.mod.json")
    lower = gradle_text.lower()
    loader = _match_coordinate_version(
        gradle_text, r"net\.fabricmc:fabric-loader:([^\"'\s)]+)"
    )
    api = _match_coordinate_version(
        gradle_text, r"net\.fabricmc\.fabric-api:fabric-api:([^\"'\s)]+)"
    )
    return {
        "present": bool(metadata) or "net.fabricmc" in lower or "fabric-api" in lower,
        "loader_version": loader,
        "fabric_api_version": api,
        "mod_id": str(metadata.get("id") or ""),
        "entrypoints": metadata.get("entrypoints", {})
        if isinstance(metadata, dict)
        else {},
        "mixins": metadata.get("mixins", []) if isinstance(metadata, dict) else [],
    }


def analyze_fabric_errors(text: str) -> list[BuildFailure]:
    lower = text.lower()
    failures: list[BuildFailure] = []
    if "fabric.mod.json" in lower and ("invalid" in lower or "missing" in lower):
        failures.append(
            BuildFailure(
                category="fabric_metadata",
                severity="error",
                summary="Fabric mod metadata appears invalid or incomplete.",
                evidence=_evidence(text, ["fabric.mod.json", "missing", "invalid"]),
                likely_causes=[
                    "`fabric.mod.json` has a missing id, entrypoint, mixin declaration, or dependency.",
                    "A refactor moved an entrypoint class without updating metadata.",
                ],
                safe_fixes=[
                    "Validate `src/main/resources/fabric.mod.json` against current package names.",
                    "Check that declared entrypoint classes still exist and implement the expected Fabric interfaces.",
                ],
                related_stack=["Fabric", "Minecraft Mod"],
            )
        )
    if (
        "mixin apply failed" in lower
        or "invalidmixin" in lower
        or "mixintransformererror" in lower
    ):
        failures.append(
            BuildFailure(
                category="fabric_mixin_failure",
                severity="error",
                summary="A Fabric Mixin failed to apply.",
                evidence=_evidence(
                    text,
                    ["Mixin apply failed", "InvalidMixin", "MixinTransformerError"],
                ),
                likely_causes=[
                    "Target class, method name, or descriptor changed between Minecraft mappings.",
                    "A client-only mixin may be loading on the wrong environment.",
                ],
                safe_fixes=[
                    "Compare the target names against the active Yarn mappings.",
                    "Check mixin environment selectors before changing injection logic.",
                ],
                related_stack=["Fabric", "Mixin", "Minecraft Mod"],
            )
        )
    if (
        "mod resolution failed" in lower
        or "fabric loader" in lower
        and "requires" in lower
    ):
        failures.append(
            BuildFailure(
                category="fabric_mod_resolution",
                severity="error",
                summary="Fabric Loader reported incompatible or missing mod dependencies.",
                evidence=_evidence(
                    text, ["Mod resolution failed", "Fabric Loader", "requires"]
                ),
                likely_causes=[
                    "The mod's dependency constraints do not match installed Minecraft/Fabric versions.",
                    "A required library mod is absent from the runtime mods folder.",
                ],
                safe_fixes=[
                    "Check dependency constraints in Fabric metadata before updating runtime jars.",
                    "Align Minecraft, Fabric Loader, Fabric API, and Yarn mapping versions together.",
                ],
                related_stack=["Fabric", "Minecraft Mod"],
            )
        )
    return failures


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _match_coordinate_version(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def _evidence(text: str, needles: list[str]) -> list[str]:
    result = []
    for line in text.splitlines():
        if any(needle.lower() in line.lower() for needle in needles):
            result.append(line.strip())
    return result[:5]


__all__ = ["analyze_fabric_errors", "detect_fabric"]
