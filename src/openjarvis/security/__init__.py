"""Security guardrails, scanners, audit, SSRF, and permissions."""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass
from typing import Any, Optional

from openjarvis.core.events import EventBus
from openjarvis.security.file_policy import (
    DEFAULT_SENSITIVE_PATTERNS,
    filter_sensitive_paths,
    is_sensitive_file,
)
from openjarvis.security.permissions import (
    PermissionDecision,
    PermissionLevel,
    PermissionMiddleware,
    PermissionRequest,
)
from openjarvis.security.types import (
    RedactionMode,
    ScanFinding,
    ScanResult,
    SecurityEvent,
    SecurityEventType,
    ThreatLevel,
)

logger = logging.getLogger(__name__)


@dataclass
class SecurityContext:
    """Result of setup_security() — wrapped engine, policy, audit."""

    engine: Any
    capability_policy: Any = None
    audit_logger: Any = None


_LAZY_EXPORTS = {
    "ApprovalQueue": ("openjarvis.security.approval_queue", "ApprovalQueue"),
    "ApprovalRecord": ("openjarvis.security.approval_queue", "ApprovalRecord"),
    "AuditLogger": ("openjarvis.security.audit", "AuditLogger"),
    "BaseScanner": ("openjarvis.security._stubs", "BaseScanner"),
    "GuardrailsEngine": ("openjarvis.security.guardrails", "GuardrailsEngine"),
    "PIIScanner": ("openjarvis.security.scanner", "PIIScanner"),
    "SecretScanner": ("openjarvis.security.scanner", "SecretScanner"),
    "SecurityBlockError": ("openjarvis.security.guardrails", "SecurityBlockError"),
    "check_ssrf": ("openjarvis.security.ssrf", "check_ssrf"),
    "is_private_ip": ("openjarvis.security.ssrf", "is_private_ip"),
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        module_name, attr_name = _LAZY_EXPORTS[name]
        value = getattr(importlib.import_module(module_name), attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'openjarvis.security' has no attribute {name!r}")


def setup_security(
    config: Any,
    engine: Any,
    bus: Optional[EventBus] = None,
) -> SecurityContext:
    """Apply security guardrails to an engine based on config."""
    if not config.security.enabled:
        return SecurityContext(engine=engine)

    try:
        from openjarvis.security._stubs import BaseScanner
        from openjarvis.security.guardrails import GuardrailsEngine
        from openjarvis.security.scanner import PIIScanner, SecretScanner

        scanners: list[BaseScanner] = []
        if config.security.secret_scanner:
            scanners.append(SecretScanner())
        if config.security.pii_scanner:
            scanners.append(PIIScanner())

        if scanners:
            mode = RedactionMode(config.security.mode)
            engine = GuardrailsEngine(
                engine,
                scanners=scanners,
                mode=mode,
                scan_input=config.security.scan_input,
                scan_output=config.security.scan_output,
                bus=bus,
            )
    except Exception as exc:
        logger.debug("Failed to set up security scanners: %s", exc)

    cap_policy = None
    if config.security.capabilities.enabled:
        try:
            from openjarvis.security.capabilities import CapabilityPolicy

            cap_policy = CapabilityPolicy(
                policy_path=config.security.capabilities.policy_path or None,
            )
        except Exception as exc:
            logger.debug("Failed to set up capability policy: %s", exc)

    audit = None
    try:
        from openjarvis.security.audit import AuditLogger

        audit = AuditLogger(
            db_path=config.security.audit_log_path,
            bus=bus,
        )
    except Exception as exc:
        logger.debug("Failed to set up audit logger: %s", exc)

    return SecurityContext(
        engine=engine,
        capability_policy=cap_policy,
        audit_logger=audit,
    )


__all__ = [
    "AuditLogger",
    "ApprovalQueue",
    "ApprovalRecord",
    "BaseScanner",
    "DEFAULT_SENSITIVE_PATTERNS",
    "GuardrailsEngine",
    "PIIScanner",
    "PermissionDecision",
    "PermissionLevel",
    "PermissionMiddleware",
    "PermissionRequest",
    "RedactionMode",
    "ScanFinding",
    "ScanResult",
    "SecretScanner",
    "SecurityBlockError",
    "SecurityContext",
    "SecurityEvent",
    "SecurityEventType",
    "ThreatLevel",
    "check_ssrf",
    "filter_sensitive_paths",
    "is_private_ip",
    "is_sensitive_file",
    "setup_security",
]
