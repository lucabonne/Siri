"""Focused workspace resolution."""

from __future__ import annotations

from pathlib import Path

from openjarvis.context import ContextLayer
from openjarvis.desktop.models import DesktopSessionState, WorkspaceFocus


class FocusResolver:
    """Resolve the current project focus from explicit input, session, or cwd."""

    def focused_workspace(
        self,
        *,
        cwd: str | Path | None = None,
        explicit_path: str | Path | None = None,
        session_state: DesktopSessionState | None = None,
    ) -> WorkspaceFocus:
        source = "explicit" if explicit_path else "cwd"
        candidate_input = explicit_path or cwd
        candidate = Path(candidate_input).expanduser() if candidate_input else None
        if (
            candidate is None
            and session_state is not None
            and session_state.focused_workspace.path
        ):
            return WorkspaceFocus(
                **{
                    **session_state.focused_workspace.to_dict(),
                    "source": "session",
                }
            )
        if candidate is None:
            candidate = Path.cwd()
        if candidate.is_file():
            candidate = candidate.parent

        try:
            context = ContextLayer(cwd=candidate).current_project_context()
            root = context.git_repository or context.cwd
            path = root or str(candidate)
            return WorkspaceFocus(
                path=path,
                name=Path(path).name,
                git_repository=context.git_repository,
                current_branch=context.current_branch,
                project_type=context.project_type,
                source=source,
            )
        except Exception:
            path = str(candidate)
            return WorkspaceFocus(path=path, name=Path(path).name, source=source)


__all__ = ["FocusResolver"]
