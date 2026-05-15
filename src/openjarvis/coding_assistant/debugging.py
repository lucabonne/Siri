"""Local-only build and debug output classification."""

# ruff: noqa: E501

from __future__ import annotations

import re

from openjarvis.coding_assistant.fabric import analyze_fabric_errors
from openjarvis.coding_assistant.gradle import analyze_gradle_errors
from openjarvis.coding_assistant.java import analyze_java_errors
from openjarvis.coding_assistant.minecraft import analyze_minecraft_errors
from openjarvis.coding_assistant.models import BuildFailure


def parse_build_errors(
    output: str, *, command: str = "", exit_code: int | None = None
) -> list[BuildFailure]:
    text = f"{command}\n{output}"
    failures: list[BuildFailure] = []
    failures.extend(analyze_gradle_errors(text))
    failures.extend(analyze_fabric_errors(text))
    failures.extend(analyze_minecraft_errors(text))
    failures.extend(analyze_java_errors(text))
    failures.extend(_node_failures(text))
    failures.extend(_rust_failures(text))
    failures.extend(_python_failures(text))
    if not failures and (exit_code not in (None, 0) or _looks_failed(text)):
        failures.append(
            BuildFailure(
                category="generic_build_failure",
                severity="error",
                summary="The build or diagnostic command failed without a specialized signature.",
                evidence=_tail_error_lines(text),
                likely_causes=[
                    "The most actionable message is likely near the last error-like lines.",
                    "A smaller targeted diagnostic command may expose a clearer failure.",
                ],
                safe_fixes=[
                    "Rerun the narrowest failing command with concise output.",
                    "Use repo search around the referenced file, symbol, or package name.",
                ],
            )
        )
    return _dedupe_failures(failures)


def debugging_steps_for(
    failures: list[BuildFailure], stack_labels: list[str]
) -> list[str]:
    steps = [
        "Start from the first unique failure, not the longest cascade.",
        "Use the repo index to find the referenced symbol, entrypoint, or manifest.",
    ]
    labels = set(stack_labels)
    categories = {failure.category for failure in failures}
    if "Gradle" in labels or any(
        category.startswith("gradle") for category in categories
    ):
        steps.append(
            "Run the smallest Gradle task that reproduces the failure before changing build files."
        )
    if {"Fabric", "Minecraft Mod"} & labels:
        steps.append(
            "Check Fabric metadata, entrypoints, mixins, and version alignment as one system."
        )
    if "Java" in labels:
        steps.append(
            "Confirm the active JDK and source/target/toolchain settings match the project."
        )
    if "Vite" in labels or "React" in labels:
        steps.append(
            "Separate type errors from bundler/runtime errors before editing components."
        )
    if "Rust" in labels:
        steps.append(
            "Use `cargo check` diagnostics as the source of truth before touching runtime logic."
        )
    if "Python" in labels:
        steps.append(
            "Read the final traceback line first, then walk upward to the first project frame."
        )
    return _dedupe(steps)


def _node_failures(text: str) -> list[BuildFailure]:
    lower = text.lower()
    failures: list[BuildFailure] = []
    if "npm err!" in lower or "pnpm" in lower and "err_" in lower:
        failures.append(
            BuildFailure(
                category="node_package_script",
                severity="error",
                summary="A Node package script or install step failed.",
                evidence=_lines_matching(text, ["npm ERR!", "ERR_PNPM", "error"]),
                likely_causes=[
                    "The package manager lockfile, Node version, or script dependency may be out of sync.",
                    "A prebuild/postinstall script may have failed locally.",
                ],
                safe_fixes=[
                    "Check the package manager named by the lockfile before reinstalling.",
                    "Inspect the first npm/pnpm error line before deleting caches or lockfiles.",
                ],
                related_stack=["Node"],
            )
        )
    if (
        "vite" in lower
        and ("failed" in lower or "error" in lower)
        or re.search(r"\bts\d{4}\b", text, re.I)
    ):
        failures.append(
            BuildFailure(
                category="vite_or_typescript",
                severity="error",
                summary="Vite or TypeScript reported a compile/bundling failure.",
                evidence=_lines_matching(text, ["vite", "TS", "Rollup", "error"]),
                likely_causes=[
                    "A TypeScript type error, missing import, or Vite plugin configuration issue blocked the build.",
                    "The referenced module may differ between dev and production resolution.",
                ],
                safe_fixes=[
                    "Run type checking separately from bundling when available.",
                    "Follow the first referenced file path before changing shared config.",
                ],
                related_stack=["Node", "Vite", "TypeScript"],
            )
        )
    return failures


def _rust_failures(text: str) -> list[BuildFailure]:
    if not re.search(r"\berror\[E\d{4}\]", text):
        return []
    return [
        BuildFailure(
            category="rust_compiler_error",
            severity="error",
            summary="Rust compiler diagnostics were detected.",
            evidence=_lines_matching(text, ["error[E", "-->", "help:"]),
            likely_causes=[
                "A type, lifetime, ownership, or missing trait bound issue blocked compilation.",
                "The first `error[E...]` often explains the real cause before follow-on errors.",
            ],
            safe_fixes=[
                "Run `cargo check` and address the first compiler error first.",
                "Read `help:` suggestions, but verify they match the module's design.",
            ],
            related_stack=["Rust"],
        )
    ]


def _python_failures(text: str) -> list[BuildFailure]:
    lower = text.lower()
    failures: list[BuildFailure] = []
    if "traceback (most recent call last)" in lower:
        failures.append(
            BuildFailure(
                category="python_traceback",
                severity="error",
                summary="Python emitted an exception traceback.",
                evidence=_tail_error_lines(text),
                likely_causes=[
                    "The final exception line names the immediate failure.",
                    "The first frame inside the repository usually points to the fix location.",
                ],
                safe_fixes=[
                    "Open the first project file in the traceback and inspect inputs around that line.",
                    "Add or run the narrowest test covering the failing code path.",
                ],
                related_stack=["Python"],
            )
        )
    if "modulenotfounderror" in lower or "importerror" in lower:
        failures.append(
            BuildFailure(
                category="python_missing_dependency",
                severity="error",
                summary="Python could not import a required module.",
                evidence=_lines_matching(text, ["ModuleNotFoundError", "ImportError"]),
                likely_causes=[
                    "The active environment is missing a dependency.",
                    "The package name or import path changed.",
                ],
                safe_fixes=[
                    "Confirm the active virtual environment before installing packages.",
                    "Check pyproject/requirements for the dependency declaration.",
                ],
                related_stack=["Python"],
            )
        )
    return failures


def _looks_failed(text: str) -> bool:
    lower = text.lower()
    return any(
        token in lower for token in ("error:", "failed", "exception", "traceback")
    )


def _lines_matching(text: str, needles: list[str]) -> list[str]:
    result = []
    for line in text.splitlines():
        if any(needle.lower() in line.lower() for needle in needles):
            result.append(line.strip())
    return result[:6]


def _tail_error_lines(text: str) -> list[str]:
    lines = [
        line.strip()
        for line in text.splitlines()
        if any(
            token in line.lower()
            for token in ("error", "failed", "exception", "traceback")
        )
    ]
    return lines[-6:]


def _dedupe_failures(failures: list[BuildFailure]) -> list[BuildFailure]:
    seen: set[str] = set()
    result: list[BuildFailure] = []
    for failure in failures:
        if failure.category not in seen:
            result.append(failure)
            seen.add(failure.category)
    return result[:12]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


__all__ = ["debugging_steps_for", "parse_build_errors"]
