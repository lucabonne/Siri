from __future__ import annotations

from pathlib import Path

from openjarvis.coding_assistant import CodingAssistantService
from openjarvis.context.terminal import TerminalContextStore
from openjarvis.repo_index import RepoIndexService


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_detects_gradle_fabric_minecraft_java21(tmp_path: Path) -> None:
    _write(
        tmp_path / "build.gradle",
        """
plugins {
    id 'fabric-loom' version '1.7-SNAPSHOT'
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

dependencies {
    minecraft "com.mojang:minecraft:1.21"
    mappings "net.fabricmc:yarn:1.21+build.9:v2"
    modImplementation "net.fabricmc:fabric-loader:0.15.11"
    modImplementation "net.fabricmc.fabric-api:fabric-api:0.100.0+1.21"
}
""",
    )
    _write(
        tmp_path / "src/main/resources/fabric.mod.json",
        '{"id": "demo", "entrypoints": {"main": ["com.example.DemoMod"]}}',
    )
    _write(
        tmp_path / "src/main/java/com/example/DemoMod.java",
        """
package com.example;

import net.fabricmc.api.ModInitializer;

public class DemoMod implements ModInitializer {
    public void onInitialize() {}
}
""",
    )

    service = CodingAssistantService(repo_index_service=RepoIndexService())
    stack = service.detect_stack(tmp_path)
    health = service.project_health_summary(tmp_path)

    assert {"Gradle", "Fabric", "Minecraft Mod", "Loom", "Java 21"} <= set(
        stack.specializations
    )
    assert stack.java_version == "21"
    assert stack.minecraft_version == "1.21"
    assert health.local_only is True
    assert health.passive_only is True
    assert health.stack.specializations


def test_coding_assistant_analyzes_build_errors_and_suggests_safe_fixes(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "build.gradle", "plugins { id 'java' }\n")
    output = """
> Task :compileJava FAILED
Execution failed for task ':compileJava'.
> error: invalid source release: 21
"""
    service = CodingAssistantService(repo_index_service=RepoIndexService())

    analysis = service.analyze_build(
        tmp_path,
        command="./gradlew build",
        output=output,
        exit_code=1,
    )

    categories = {failure.category for failure in analysis.failures}
    assert analysis.has_failure is True
    assert "gradle_task_failure" in categories
    assert "java_gradle_version_mismatch" in categories
    assert analysis.suggested_fixes
    assert all(fix.passive_only for fix in analysis.suggested_fixes)
    assert any(fix.command for fix in analysis.suggested_fixes)


def test_coding_panel_uses_terminal_context(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", "[project]\ndependencies = []\n")
    _write(tmp_path / "src/app.py", "def main():\n    return None\n")
    terminal = TerminalContextStore(history_path=tmp_path / "terminal.jsonl")
    terminal.record(
        command="python -m pytest",
        output=(
            "Traceback (most recent call last):\n"
            "ModuleNotFoundError: No module named 'rich'\n"
        ),
        exit_code=1,
        cwd=tmp_path,
    )
    service = CodingAssistantService(
        repo_index_service=RepoIndexService(),
        terminal_store=terminal,
    )

    panel = service.coding_panel(tmp_path)

    assert panel.local_only is True
    assert panel.passive_only is True
    assert panel.cloud_uploaded is False
    assert panel.recent_errors
    assert panel.architecture_overview is not None
    assert panel.build_health.has_failure is True
