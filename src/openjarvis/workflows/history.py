"""File-backed workflow run history."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from openjarvis.security.file_utils import secure_create
from openjarvis.workflows.models import WorkflowRun


class WorkflowHistoryStore:
    """Persist workflow runs as JSONL under ``~/.openjarvis``."""

    def __init__(self, history_path: str | Path | None = None) -> None:
        self.history_path = (
            Path(history_path).expanduser()
            if history_path is not None
            else Path.home() / ".openjarvis" / "workflow_history.jsonl"
        )

    def append(self, run: WorkflowRun) -> None:
        path = secure_create(self.history_path)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(run.to_dict(), sort_keys=True) + "\n")

    def latest(self, *, limit: int = 50) -> list[WorkflowRun]:
        runs = list(self._iter_runs())
        runs.sort(key=lambda run: run.requested_at, reverse=True)
        return runs[: max(0, limit)]

    def get(self, run_id: str) -> WorkflowRun:
        for run in self._iter_runs():
            if run.id == run_id:
                return run
        raise KeyError(run_id)

    def latest_for_workflow(
        self,
        workflow_id: str,
        *,
        limit: int = 20,
    ) -> list[WorkflowRun]:
        runs = [run for run in self.latest(limit=500) if run.workflow_id == workflow_id]
        return runs[: max(0, limit)]

    def _iter_runs(self) -> Iterable[WorkflowRun]:
        if not self.history_path.exists():
            return
        for line in self.history_path.read_text(encoding="utf-8").splitlines():
            try:
                yield WorkflowRun.from_mapping(json.loads(line))
            except Exception:
                continue


__all__ = ["WorkflowHistoryStore"]
