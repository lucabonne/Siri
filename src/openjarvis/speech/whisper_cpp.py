"""whisper.cpp speech-to-text backend (local subprocess based)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from openjarvis.core.registry import SpeechRegistry
from openjarvis.speech._stubs import SpeechBackend, TranscriptionResult


def _find_binary() -> str:
    configured = os.environ.get("WHISPER_CPP_BINARY", "").strip()
    if configured:
        return configured
    for candidate in ("whisper-cli", "whisper-cpp", "main"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return ""


@SpeechRegistry.register("whisper.cpp")
class WhisperCppBackend(SpeechBackend):
    """Local transcription using an installed whisper.cpp binary."""

    backend_id = "whisper.cpp"

    def __init__(
        self,
        *,
        binary_path: str = "",
        model_path: str = "",
        timeout_seconds: int = 180,
    ) -> None:
        self._binary_path = binary_path or _find_binary()
        self._model_path = model_path or os.environ.get("WHISPER_CPP_MODEL", "")
        self._timeout_seconds = timeout_seconds

    def transcribe(
        self,
        audio: bytes,
        *,
        format: str = "wav",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        if not self.health():
            raise RuntimeError(
                "whisper.cpp is not configured. Set WHISPER_CPP_BINARY and "
                "WHISPER_CPP_MODEL, or install whisper-cli on PATH."
            )

        suffix = f".{format.lstrip('.') or 'wav'}"
        with tempfile.TemporaryDirectory(prefix="openjarvis-whisper-cpp-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            audio_path = tmp_path / f"audio{suffix}"
            out_base = tmp_path / "transcript"
            audio_path.write_bytes(audio)
            command = [
                self._binary_path,
                "-m",
                self._model_path,
                "-f",
                str(audio_path),
                "-otxt",
                "-of",
                str(out_base),
            ]
            if language:
                command.extend(["-l", language])
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
            transcript_path = out_base.with_suffix(".txt")
            text = (
                transcript_path.read_text(encoding="utf-8").strip()
                if transcript_path.exists()
                else ""
            )
            if result.returncode != 0 and not text:
                detail = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(f"whisper.cpp transcription failed: {detail}")
            return TranscriptionResult(text=text)

    def health(self) -> bool:
        return bool(
            self._binary_path
            and self._model_path
            and Path(self._model_path).expanduser().exists()
        )

    def supported_formats(self) -> List[str]:
        return ["wav", "mp3", "m4a", "ogg", "flac", "webm"]


__all__ = ["WhisperCppBackend"]
