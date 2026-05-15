from __future__ import annotations

import subprocess
from pathlib import Path

from openjarvis.memory import MemoryService
from openjarvis.repo_index import RepoIndexService


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_repo_index_detects_gradle_fabric_minecraft_mod(tmp_path: Path) -> None:
    _write(
        tmp_path / "build.gradle",
        """
plugins {
    id 'fabric-loom' version '1.7-SNAPSHOT'
}
dependencies {
    minecraft "com.mojang:minecraft:1.21"
    modImplementation "net.fabricmc:fabric-loader:0.15.11"
    modImplementation "net.fabricmc.fabric-api:fabric-api:0.100.0+1.21"
}
""",
    )
    _write(tmp_path / "settings.gradle", "pluginManagement { repositories {} }\n")
    _write(
        tmp_path / "src/main/java/com/example/DemoMod.java",
        """
package com.example;

import net.fabricmc.api.ModInitializer;

public class DemoMod implements ModInitializer {
    @Override
    public void onInitialize() {}
}
""",
    )
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True)

    summary = RepoIndexService().repo_summary(tmp_path)

    assert summary.git_repository == str(tmp_path)
    assert summary.current_branch == "main"
    assert summary.detected_stack.project_type == "minecraft mod"
    assert "Java" in summary.detected_stack.frameworks
    assert "Gradle" in summary.detected_stack.build_systems
    assert {"Fabric", "Loom", "Minecraft Mod"} <= set(summary.detected_stack.frameworks)
    assert "Gradle" in summary.detected_stack.package_managers
    assert "src/main/java/com/example/DemoMod.java" in summary.architecture.entry_points


def test_repo_index_avoids_ignored_and_sensitive_paths(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", "[project]\ndependencies = []\n")
    _write(tmp_path / "src/app.py", "def run():\n    return 'ok'\n")
    _write(tmp_path / ".env", "TOKEN=secret\n")
    _write(tmp_path / "node_modules/pkg/index.js", "ignored\n")

    summary = RepoIndexService().repo_summary(tmp_path)
    paths = {item.path for item in summary.file_summaries}

    assert "src/app.py" in paths
    assert ".env" not in paths
    assert "node_modules/pkg/index.js" not in paths
    assert ".env" in summary.skipped_paths


def test_repo_semantic_search_finds_symbols(tmp_path: Path) -> None:
    _write(
        tmp_path / "src/openjarvis/repo.py",
        "class RepoIndexer:\n    def semantic_search(self):\n        return []\n",
    )
    _write(
        tmp_path / "src/openjarvis/voice.py",
        "def record_audio():\n    return None\n",
    )

    service = RepoIndexService()
    results = service.semantic_search("semantic repo indexer", tmp_path, limit=3)

    assert results
    assert results[0].path == "src/openjarvis/repo.py"
    assert "RepoIndexer" in results[0].symbols


def test_repo_index_can_record_memory_snapshot(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", "[project]\ndependencies = []\n")
    _write(tmp_path / "src/app.py", "print('hello')\n")
    memory = MemoryService(db_path=tmp_path / "memory.db", enable_semantic=False)
    try:
        service = RepoIndexService(memory_service=memory)
        summary = service.index_repository(tmp_path, persist_memory=True)
        snapshots = memory.list_repo_index_snapshots(repo_root=summary.root)
    finally:
        memory.close()

    assert snapshots
    assert snapshots[0]["summary"]["indexed_file_count"] >= 1
    assert snapshots[0]["local_only"] is True
