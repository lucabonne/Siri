"""File-backed approval queue for permission-gated tool calls."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from openjarvis.security.file_utils import secure_create, secure_mkdir
from openjarvis.security.permissions import PermissionDecision, PermissionRequest


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ApprovalRecord:
    """A persisted tool approval request."""

    id: str
    status: str
    requested_at: str
    decided_at: Optional[str]
    tool: str
    agent_id: str
    source: str
    level: str
    reason: str
    matched_pattern: Optional[str]
    argument_keys: list[str]
    command_preview: str
    decision: Optional[str] = None
    decision_note: str = ""

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> "ApprovalRecord":
        return cls(
            id=str(data.get("id", "")),
            status=str(data.get("status", "pending")),
            requested_at=str(data.get("requested_at", "")),
            decided_at=data.get("decided_at"),
            tool=str(data.get("tool", "")),
            agent_id=str(data.get("agent_id", "")),
            source=str(data.get("source", "")),
            level=str(data.get("level", "")),
            reason=str(data.get("reason", "")),
            matched_pattern=data.get("matched_pattern"),
            argument_keys=[str(item) for item in data.get("argument_keys", [])],
            command_preview=str(data.get("command_preview", "")),
            decision=data.get("decision"),
            decision_note=str(data.get("decision_note", "")),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "requested_at": self.requested_at,
            "decided_at": self.decided_at,
            "tool": self.tool,
            "agent_id": self.agent_id,
            "source": self.source,
            "level": self.level,
            "reason": self.reason,
            "matched_pattern": self.matched_pattern,
            "argument_keys": self.argument_keys,
            "command_preview": self.command_preview,
            "decision": self.decision,
            "decision_note": self.decision_note,
        }


class ApprovalQueue:
    """Persist and mutate approval records under ``~/.openjarvis``."""

    def __init__(self, queue_dir: Path | str | None = None) -> None:
        self._dir = (
            Path(queue_dir).expanduser()
            if queue_dir is not None
            else Path.home() / ".openjarvis" / "approvals"
        )
        secure_mkdir(self._dir)

    @property
    def queue_dir(self) -> Path:
        return self._dir

    def enqueue(
        self,
        request: PermissionRequest,
        decision: PermissionDecision,
        *,
        source: str = "",
    ) -> ApprovalRecord:
        """Write a pending approval record and return it."""
        arguments = request.arguments if isinstance(request.arguments, Mapping) else {}
        requested_at = _now()
        record = ApprovalRecord(
            id=self._make_id(request, decision, requested_at),
            status="pending",
            requested_at=requested_at,
            decided_at=None,
            tool=request.tool_name,
            agent_id=request.agent_id,
            source=source or str(request.metadata.get("source", "")),
            level=decision.level.name,
            reason=decision.reason,
            matched_pattern=decision.matched_pattern,
            argument_keys=sorted(str(key) for key in arguments.keys()),
            command_preview=self._command_preview(request, arguments),
        )
        self._write(record)
        return record

    def list(
        self,
        *,
        status: str = "pending",
        limit: int = 50,
    ) -> list[ApprovalRecord]:
        """Return approval records, newest first."""
        records = list(self._iter_records())
        if status != "all":
            records = [record for record in records if record.status == status]
        records.sort(key=lambda record: record.requested_at, reverse=True)
        return records[: max(0, limit)]

    def decide(
        self,
        approval_id: str,
        decision: str,
        *,
        note: str = "",
    ) -> ApprovalRecord:
        """Mark a pending approval as approved or denied."""
        if decision not in {"approved", "denied"}:
            raise ValueError("decision must be 'approved' or 'denied'")

        record = self.get(approval_id)
        if record.status != "pending":
            raise ValueError(f"approval is already {record.status}")

        record.status = decision
        record.decision = decision
        record.decision_note = note
        record.decided_at = _now()
        self._write(record)
        return record

    def get(self, approval_id: str) -> ApprovalRecord:
        path = self._path_for(approval_id)
        if not path.exists():
            raise KeyError(approval_id)
        return ApprovalRecord.from_json(json.loads(path.read_text(encoding="utf-8")))

    def _iter_records(self) -> Iterable[ApprovalRecord]:
        for path in self._dir.glob("*.json"):
            try:
                yield ApprovalRecord.from_json(
                    json.loads(path.read_text(encoding="utf-8"))
                )
            except Exception:
                continue

    def _write(self, record: ApprovalRecord) -> None:
        path = secure_create(self._path_for(record.id))
        path.write_text(
            json.dumps(record.to_json(), sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _path_for(self, approval_id: str) -> Path:
        safe_id = "".join(ch for ch in approval_id if ch.isalnum() or ch in {"-", "_"})
        return self._dir / f"{safe_id}.json"

    @staticmethod
    def _make_id(
        request: PermissionRequest,
        decision: PermissionDecision,
        requested_at: str,
    ) -> str:
        seed = json.dumps(
            {
                "requested_at": requested_at,
                "tool": request.tool_name,
                "agent_id": request.agent_id,
                "command": request.command,
                "arguments": request.arguments,
                "reason": decision.reason,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _command_preview(
        request: PermissionRequest,
        arguments: Mapping[str, Any],
    ) -> str:
        command = request.command
        if command is None:
            raw = (
                arguments.get("command")
                or arguments.get("cmd")
                or arguments.get("script")
            )
            command = raw if isinstance(raw, str) else ""
        return (command or "")[:200]


__all__ = ["ApprovalQueue", "ApprovalRecord"]
