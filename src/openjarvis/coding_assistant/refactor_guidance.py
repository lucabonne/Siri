"""Passive safe-fix and refactor guidance."""

# ruff: noqa: E501

from __future__ import annotations

from openjarvis.coding_assistant.models import BuildFailure, SafeFixSuggestion


def safe_fix_suggestions(failures: list[BuildFailure]) -> list[SafeFixSuggestion]:
    suggestions: list[SafeFixSuggestion] = []
    for failure in failures:
        suggestions.append(
            SafeFixSuggestion(
                title=_title_for(failure.category),
                rationale=failure.summary,
                steps=failure.safe_fixes
                or ["Inspect the cited evidence before editing code."],
                risk=_risk_for(failure.category),
            )
        )
    if not suggestions:
        suggestions.append(
            SafeFixSuggestion(
                title="Review project health signals",
                rationale="No active build failure was detected.",
                steps=[
                    "Use the architecture overview to choose a narrow entry point.",
                    "Run the smallest existing test or build command before changing behavior.",
                ],
                risk="low",
            )
        )
    return suggestions[:8]


def risky_refactor_guidance(labels: list[str]) -> list[str]:
    label_set = set(labels)
    guidance: list[str] = []
    if "Gradle" in label_set:
        guidance.append(
            "Treat build-script edits as high leverage; inspect task and dependency effects first."
        )
    if "Fabric" in label_set or "Minecraft Mod" in label_set:
        guidance.append(
            "Keep metadata, entrypoint classes, mixins, and mappings synchronized during package moves."
        )
    if "Java" in label_set:
        guidance.append(
            "Prefer small Java API changes with compile checks between each step."
        )
    if "Vite" in label_set or "Node" in label_set:
        guidance.append("Separate type-only refactors from bundler/config changes.")
    if "Rust" in label_set:
        guidance.append(
            "Move Rust modules together with `mod` declarations and workspace manifests."
        )
    if "Python" in label_set:
        guidance.append(
            "Preserve import paths or add transitional aliases when moving Python modules."
        )
    return guidance[:8]


def _title_for(category: str) -> str:
    words = category.replace("_", " ").strip()
    return words[:1].upper() + words[1:] if words else "Safe diagnostic"


def _risk_for(category: str) -> str:
    if any(token in category for token in ("gradle", "mixin", "mapping", "version")):
        return "medium"
    return "low"


__all__ = ["risky_refactor_guidance", "safe_fix_suggestions"]
