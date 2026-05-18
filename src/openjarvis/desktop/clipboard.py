"""Local clipboard helpers for desktop context."""

from __future__ import annotations

import platform
import subprocess

from openjarvis.context.layer import ContextLayer


class ClipboardProvider:
    """Read a small local clipboard preview on explicit status requests."""

    def preview(self, *, privacy_mode: bool = False) -> tuple[str, bool]:
        if platform.system() != "Darwin":
            return "", False
        try:
            result = subprocess.run(
                ["pbpaste"],
                check=False,
                capture_output=True,
                text=True,
                timeout=0.6,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "", False
        if result.returncode != 0:
            return "", False
        return ContextLayer.sanitize_clipboard(
            result.stdout,
            privacy_mode=privacy_mode,
        )


__all__ = ["ClipboardProvider"]
