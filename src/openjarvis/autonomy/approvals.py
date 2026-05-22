"""Approval management for the autonomy layer."""

import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

from openjarvis.autonomy.models import utc_now


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    id: str
    plan_id: str
    step_id: str
    reason: str
    status: str = "pending" # pending, approved, denied
    created_at: str = field(default_factory=utc_now)
    resolved_at: str | None = None

    def to_dict(self):
        return asdict(self)

class ApprovalManager:
    def __init__(self):
        self._approvals: dict[str, ApprovalRequest] = {}

    def request_approval(
        self, plan_id: str, step_id: str, reason: str
    ) -> ApprovalRequest:
        req_id = str(uuid.uuid4())
        req = ApprovalRequest(
            id=req_id,
            plan_id=plan_id,
            step_id=step_id,
            reason=reason
        )
        self._approvals[req_id] = req
        return req

    def get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._approvals.get(approval_id)

    def list_pending_approvals(self) -> list[ApprovalRequest]:
        return [a for a in self._approvals.values() if a.status == "pending"]

    def resolve_approval(
        self, approval_id: str, approved: bool
    ) -> Optional[ApprovalRequest]:
        req = self._approvals.get(approval_id)
        if not req or req.status != "pending":
            return None

        status = "approved" if approved else "denied"
        updated = ApprovalRequest(
            id=req.id,
            plan_id=req.plan_id,
            step_id=req.step_id,
            reason=req.reason,
            status=status,
            created_at=req.created_at,
            resolved_at=utc_now()
        )
        self._approvals[approval_id] = updated
        return updated

approval_manager = ApprovalManager()
