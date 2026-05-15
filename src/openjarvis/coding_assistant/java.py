"""Java and Java 21 passive project intelligence."""

# ruff: noqa: E501

from __future__ import annotations

import re
from pathlib import Path

from openjarvis.coding_assistant.gradle import read_gradle_text
from openjarvis.coding_assistant.models import BuildFailure


def detect_java(root: str | Path) -> dict[str, str | bool]:
    root_path = Path(root)
    text = read_gradle_text(root)
    version = _first(
        text,
        [
            r"JavaLanguageVersion\.of\((\d+)\)",
            r"sourceCompatibility\s*=\s*['\"]?(?:JavaVersion\.VERSION_)?(\d+)",
            r"targetCompatibility\s*=\s*['\"]?(?:JavaVersion\.VERSION_)?(\d+)",
            r"java_version\s*=\s*(\d+)",
        ],
    )
    return {
        "present": bool(version)
        or (root_path / "src/main/java").exists()
        or (root_path / "src/test/java").exists(),
        "version": version,
        "java_21": version == "21",
        "uses_toolchains": "toolchain" in text.lower() or "JavaLanguageVersion" in text,
    }


def analyze_java_errors(text: str) -> list[BuildFailure]:
    lower = text.lower()
    failures: list[BuildFailure] = []
    if "cannot find symbol" in lower:
        failures.append(
            BuildFailure(
                category="java_symbol_resolution",
                severity="error",
                summary="Java compilation could not resolve a symbol.",
                evidence=_evidence(
                    text, ["cannot find symbol", "symbol:", "location:"]
                ),
                likely_causes=[
                    "A class, method, field, or import was renamed or not on the compile classpath.",
                    "Generated or mod-loader classes may not be available for the active source set.",
                ],
                safe_fixes=[
                    "Start at the first `cannot find symbol` block and inspect imports/package names.",
                    "Check dependency and source-set wiring before broad refactors.",
                ],
                related_stack=["Java"],
            )
        )
    if "package " in lower and " does not exist" in lower:
        failures.append(
            BuildFailure(
                category="java_missing_package",
                severity="error",
                summary="Java compilation references a package that is not on the classpath.",
                evidence=_evidence(text, ["package", "does not exist"]),
                likely_causes=[
                    "A dependency scope is missing or a package moved between versions.",
                    "A source-set dependency is not wired into the compile task.",
                ],
                safe_fixes=[
                    "Verify the missing package owner in the dependency graph.",
                    "Avoid changing imports until the classpath/dependency version is confirmed.",
                ],
                related_stack=["Java", "Gradle"],
            )
        )
    return failures


def _first(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _evidence(text: str, needles: list[str]) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if any(needle.lower() in line.lower() for needle in needles)
    ][:5]


__all__ = ["analyze_java_errors", "detect_java"]
