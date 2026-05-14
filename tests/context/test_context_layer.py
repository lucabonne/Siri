from __future__ import annotations

import subprocess
from pathlib import Path

from openjarvis.context import ContextLayer


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_project_context_detects_repo_stack_and_branch(tmp_path: Path) -> None:
    _write(
        tmp_path / "pyproject.toml",
        """
[project]
dependencies = ["fastapi>=0.110", "pytest>=8"]
""",
    )
    _write(
        tmp_path / "frontend" / "package.json",
        (
            '{"dependencies": {"@tauri-apps/api": "^2.0.0", '
            '"react": "^19.0.0", "vite": "^7.0.0"}}'
        ),
    )
    _write(tmp_path / "rust" / "Cargo.toml", "[package]\nname = \"demo\"\n")
    _write(tmp_path / "src" / "demo" / "api.py", "from fastapi import FastAPI\n")
    _write(
        tmp_path / "frontend" / "src" / "App.tsx",
        "export function App() { return null }\n",
    )

    subprocess.run(
        ["git", "init", "-b", "main"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )

    context = ContextLayer(cwd=tmp_path).current_project_context()

    assert context.git_repository == str(tmp_path)
    assert context.current_branch == "main"
    assert "Python" in context.languages
    assert "TypeScript" in context.languages
    assert {"FastAPI", "React", "Tauri", "Vite"} <= set(context.framework_build_system)
    assert {"pip/uv", "npm", "Cargo"} <= set(context.package_manager)
    assert context.project_type == "desktop app"


def test_repo_index_builds_inventory_and_dependency_hints(tmp_path: Path) -> None:
    _write(
        tmp_path / "pyproject.toml",
        "[project]\ndependencies = [\"fastapi>=0.110\"]\n",
    )
    _write(tmp_path / "src" / "app.py", "print('hello')\n")
    _write(tmp_path / "tests" / "test_app.py", "def test_app(): pass\n")
    _write(tmp_path / "node_modules" / "ignored.js", "ignored\n")

    index = ContextLayer(cwd=tmp_path).repo_index()

    assert "src/app.py" in index.inventory
    assert "node_modules/ignored.js" not in index.inventory
    assert "fastapi" in index.dependency_hints
    assert index.architecture_metadata["has_backend"] is True
    assert index.architecture_metadata["has_tests"] is True
    assert any(summary["name"] == "src" for summary in index.module_summaries)


def test_clipboard_preview_redacts_sensitive_content() -> None:
    preview, sensitive = ContextLayer.sanitize_clipboard(
        "api_key=sk-testsecret1234567890"
    )

    assert preview == "[redacted clipboard]"
    assert sensitive is True


def test_clipboard_preview_redacts_when_privacy_mode_is_active() -> None:
    preview, sensitive = ContextLayer.sanitize_clipboard(
        "normal clipboard text",
        privacy_mode=True,
    )

    assert preview == "[redacted clipboard]"
    assert sensitive is True
