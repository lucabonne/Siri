"""Passive local screenshot capture and visual context metadata.

The vision layer captures only when explicitly requested. It stores screenshot
bytes locally and exposes metadata for Mission Control; it never uploads image
data or starts a watcher.
"""

from __future__ import annotations

import hashlib
import json
import platform
import struct
import subprocess
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from openjarvis.context.layer import ContextLayer
from openjarvis.context.models import ScreenshotMetadata, VisualContext
from openjarvis.security.file_utils import secure_create, secure_mkdir


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp_id(captured_at: str) -> str:
    return (
        captured_at.replace("+00:00", "Z")
        .replace(":", "")
        .replace("-", "")
        .replace(".", "")
    )


def _png_size(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
    except OSError:
        return None, None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None, None
    try:
        return struct.unpack(">II", header[16:24])
    except struct.error:
        return None, None


def _metadata_from_dict(data: Mapping[str, Any]) -> ScreenshotMetadata:
    keys = {field.name for field in fields(ScreenshotMetadata)}
    filtered = {key: value for key, value in data.items() if key in keys}
    return ScreenshotMetadata(
        id=str(filtered.get("id", "")),
        captured_at=str(filtered.get("captured_at", _now())),
        file_path=str(filtered.get("file_path", "")),
        format=str(filtered.get("format", "png")),
        width=(
            int(filtered["width"])
            if filtered.get("width") is not None
            else None
        ),
        height=(
            int(filtered["height"])
            if filtered.get("height") is not None
            else None
        ),
        byte_size=(
            int(filtered["byte_size"])
            if filtered.get("byte_size") is not None
            else None
        ),
        sha256=str(filtered.get("sha256", "")),
        active_application=str(filtered.get("active_application", "")),
        active_window_title=str(filtered.get("active_window_title", "")),
        privacy_mode=bool(filtered.get("privacy_mode", False)),
        redacted=bool(filtered.get("redacted", False)),
        passive_only=bool(filtered.get("passive_only", True)),
        local_only=bool(filtered.get("local_only", True)),
    )


class VisionContextStore:
    """Local-only screenshot capture and metadata persistence."""

    def __init__(
        self,
        *,
        root_dir: Path | str | None = None,
        metadata_path: Path | str | None = None,
    ) -> None:
        base = (
            Path(root_dir).expanduser()
            if root_dir
            else Path.home() / ".openjarvis" / "vision"
        )
        self.root_dir = secure_mkdir(base)
        self.screenshot_dir = secure_mkdir(self.root_dir / "screenshots")
        self.metadata_path = (
            Path(metadata_path).expanduser()
            if metadata_path is not None
            else self.root_dir / "screenshots.jsonl"
        )
        secure_create(self.metadata_path)

    def capture(
        self,
        *,
        cwd: str | Path | None = None,
        privacy_mode: bool = False,
    ) -> ScreenshotMetadata:
        """Capture a single macOS screenshot after explicit user/API request."""
        if privacy_mode:
            raise PermissionError("privacy mode requires approval before screenshots")
        if platform.system() != "Darwin":
            raise RuntimeError("local screenshot capture is only implemented on macOS")

        captured_at = _now()
        screenshot_id = _timestamp_id(captured_at)
        path = self.screenshot_dir / f"{screenshot_id}.png"
        self._run_capture(path)

        data = path.read_bytes()
        width, height = _png_size(path)
        active_app, window_title = ContextLayer(cwd=cwd)._active_macos_window()
        metadata = ScreenshotMetadata(
            id=screenshot_id,
            captured_at=captured_at,
            file_path=str(path),
            format="png",
            width=width,
            height=height,
            byte_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            active_application=active_app,
            active_window_title=window_title,
            privacy_mode=False,
        )
        self._append(metadata)
        return metadata

    def recent(
        self,
        *,
        limit: int = 10,
        privacy_mode: bool = False,
    ) -> list[ScreenshotMetadata]:
        records = list(self._read_all())[-limit:]
        records.reverse()
        if privacy_mode:
            return [record.redacted_copy() for record in records]
        return records

    def latest_context(self, *, privacy_mode: bool = False) -> VisualContext:
        records = list(self._read_all())
        latest = records[-1] if records else None
        if latest is not None and privacy_mode:
            latest = latest.redacted_copy()
        return VisualContext(
            latest_screenshot=latest,
            screenshot_count=len(records),
            privacy_mode=privacy_mode,
        )

    def _run_capture(self, path: Path) -> None:
        try:
            result = subprocess.run(
                ["screencapture", "-x", str(path)],
                check=False,
                capture_output=True,
                text=True,
                timeout=5.0,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("macOS screenshot capture failed") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(detail or "macOS screenshot capture failed")

    def _append(self, metadata: ScreenshotMetadata) -> None:
        secure_create(self.metadata_path)
        with self.metadata_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(metadata.to_dict(), sort_keys=True) + "\n")

    def _read_all(self) -> Iterable[ScreenshotMetadata]:
        if not self.metadata_path.exists():
            return []
        records: list[ScreenshotMetadata] = []
        for line in self.metadata_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(_metadata_from_dict(json.loads(line)))
            except Exception:
                continue
        return records


__all__ = ["VisionContextStore"]
