"""Gradle-specific passive detection and error hints."""

# ruff: noqa: E501

from __future__ import annotations

import re
from pathlib import Path

from openjarvis.coding_assistant.models import BuildFailure

GRADLE_FILES = (
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
)


def read_gradle_text(root: str | Path, *, max_chars: int = 120_000) -> str:
    root_path = Path(root)
    chunks: list[str] = []
    for rel in GRADLE_FILES:
        path = root_path / rel
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks)[:max_chars]


def detect_gradle(root: str | Path) -> dict[str, str | bool]:
    text = read_gradle_text(root)
    lower = text.lower()
    wrapper = (Path(root) / "gradlew").exists() or (Path(root) / "gradlew.bat").exists()
    version = _first_match(text, r"gradle-([0-9][0-9.]+)-")
    return {
        "present": bool(text) or wrapper,
        "wrapper_present": wrapper,
        "version": version,
        "uses_kotlin_dsl": (Path(root) / "build.gradle.kts").exists(),
        "uses_fabric_loom": "fabric-loom" in lower,
    }


def analyze_gradle_errors(text: str) -> list[BuildFailure]:
    lower = text.lower()
    failures: list[BuildFailure] = []
    if "execution failed for task" in lower:
        task = _first_match(text, r"Execution failed for task '([^']+)'")
        failures.append(
            BuildFailure(
                category="gradle_task_failure",
                severity="error",
                summary=f"Gradle task failed{f': {task}' if task else ''}.",
                evidence=_evidence(
                    text, ["Execution failed for task", "* What went wrong:"]
                ),
                likely_causes=[
                    "The failing task reported a compile, resource, or dependency error.",
                    "The actionable message is usually in the lines immediately above the task failure.",
                ],
                safe_fixes=[
                    "Rerun the smallest failing Gradle task with stacktrace enabled.",
                    "Inspect changed build scripts and dependency coordinates before editing source.",
                ],
                related_stack=["Gradle"],
            )
        )
    if "could not resolve" in lower or "could not find" in lower:
        failures.append(
            BuildFailure(
                category="gradle_dependency_resolution",
                severity="error",
                summary="Gradle could not resolve one or more dependencies.",
                evidence=_evidence(text, ["Could not resolve", "Could not find"]),
                likely_causes=[
                    "A repository is missing, offline, or blocked.",
                    "A dependency coordinate or version is not available for this Minecraft/Fabric version.",
                ],
                safe_fixes=[
                    "Check repository declarations before changing versions.",
                    "Verify Fabric API, loader, Loom, and Minecraft versions are compatible.",
                ],
                related_stack=["Gradle"],
            )
        )
    if (
        "unsupported class file major version" in lower
        or "invalid source release" in lower
    ):
        failures.append(
            BuildFailure(
                category="java_gradle_version_mismatch",
                severity="error",
                summary="Gradle or javac appears to be using an incompatible Java version.",
                evidence=_evidence(
                    text,
                    ["Unsupported class file major version", "invalid source release"],
                ),
                likely_causes=[
                    "The Gradle daemon is running on a JDK older than the project target.",
                    "The toolchain/sourceCompatibility setting does not match Java 21.",
                ],
                safe_fixes=[
                    "Confirm `java -version` and `./gradlew -version` both report the expected JDK.",
                    "Prefer Gradle toolchains over relying on shell JAVA_HOME.",
                ],
                related_stack=["Gradle", "Java"],
            )
        )
    return failures


def gradle_safe_commands(root: str | Path) -> list[tuple[str, str]]:
    command = "./gradlew" if (Path(root) / "gradlew").exists() else "gradle"
    return [
        (f"{command} --version", "Check the Gradle runtime and JVM without building."),
        (
            f"{command} tasks --all",
            "List available tasks to identify the smallest diagnostic target.",
        ),
    ]


def _first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _evidence(text: str, needles: list[str]) -> list[str]:
    lines = []
    for line in text.splitlines():
        if any(needle.lower() in line.lower() for needle in needles):
            lines.append(line.strip())
    return lines[:5]


__all__ = [
    "GRADLE_FILES",
    "analyze_gradle_errors",
    "detect_gradle",
    "gradle_safe_commands",
    "read_gradle_text",
]
