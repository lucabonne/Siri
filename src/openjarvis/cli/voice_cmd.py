"""``jarvis voice`` - explicit local/manual voice bridge commands."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
import time
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
import httpx

from openjarvis.core.config import load_config
from openjarvis.hotkeys.macos_bridge import (
    MacOSHotkeyBridgeCommand,
    validate_hammerspoon_bridge,
)
from openjarvis.voice.event_log import (
    VoiceEventLogger,
    cleanup_voice_events,
    query_voice_events,
    voice_log_settings_from_config,
)
from openjarvis.voice.models import TranscriptionUnavailableError, VoiceRecordingError
from openjarvis.voice.recorder import (
    MICROPHONE_MAX_DURATION_SECONDS,
    MICROPHONE_MIN_DURATION_SECONDS,
    MICROPHONE_RECORDER_KINDS,
    RECORDER_KINDS,
    LocalMacOSRecorder,
    Recorder,
    SilentWavRecorder,
    SoundDeviceRecorder,
    inspect_wav_file,
    microphone_recording_policy,
    recorder_diagnostics,
)
from openjarvis.voice.speech_output import (
    LOCAL_SPEECH_OUTPUT_ADAPTERS,
    LocalSpeechOutput,
    SpeechOutputUnavailableError,
    build_local_speech_output,
)
from openjarvis.voice.transcription import (
    LOCAL_TRANSCRIPTION_ADAPTERS,
    SpeechBackendLocalTranscriptionAdapter,
    resolve_local_transcription_adapter_id,
)


def _base_url(override: str | None) -> str:
    if override:
        return override.rstrip("/")

    config = load_config()
    voice_control = getattr(config, "voice_control", None)
    configured_base = getattr(voice_control, "default_api_base_url", "")
    if configured_base:
        return str(configured_base).rstrip("/")

    host = config.server.host
    if host in {"0.0.0.0", "::", ""}:
        host = "127.0.0.1"
    return f"http://{host}:{config.server.port}"


def _api_key(override: str | None) -> str:
    if override:
        return override
    env_key = os.environ.get("OPENJARVIS_API_KEY", "")
    if env_key:
        return env_key

    try:
        import tomllib

        config_path = Path.home() / ".openjarvis" / "config.toml"
        raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
        return raw.get("server", {}).get("auth", {}).get("api_key", "")
    except (FileNotFoundError, OSError, ImportError, UnicodeDecodeError):
        return ""


def _headers(api_key: str) -> dict[str, str]:
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def _post_json(
    endpoint: str,
    payload: dict[str, Any] | None,
    *,
    base_url: str,
    api_key: str,
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        response = httpx.post(
            url,
            json=payload or {},
            headers=_headers(api_key),
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        raise click.ClickException(
            f"{endpoint} returned HTTP {exc.response.status_code}: {body}"
        ) from exc
    except httpx.RequestError as exc:
        raise click.ClickException(f"Could not reach {base_url}: {exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise click.ClickException(f"{endpoint} returned non-JSON response") from exc


def _get_json(
    endpoint: str,
    *,
    base_url: str,
    api_key: str,
    timeout: float,
) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        response = httpx.get(url, headers=_headers(api_key), timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text
        raise click.ClickException(
            f"{endpoint} returned HTTP {exc.response.status_code}: {body}"
        ) from exc
    except httpx.RequestError as exc:
        raise click.ClickException(f"Could not reach {base_url}: {exc}") from exc

    try:
        return response.json()
    except ValueError as exc:
        raise click.ClickException(f"{endpoint} returned non-JSON response") from exc


def _emit_json(data: dict[str, Any]) -> None:
    click.echo(json.dumps(data, indent=2, sort_keys=True))


def _voice_logs_export_format(path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    return "json" if path.suffix.lower() == ".json" else "jsonl"


def _validate_voice_logs_export_path(path: Path) -> None:
    if not str(path):
        raise click.ClickException("Export path is required")
    if "://" in str(path):
        raise click.ClickException("Export path must be a local filesystem path")
    if path.exists() and path.is_dir():
        raise click.ClickException(f"Export path is a directory: {path}")
    parent = path.parent if str(path.parent) else Path(".")
    if not parent.exists():
        raise click.ClickException(
            f"Export parent directory does not exist: {parent}. "
            "Create it first, then rerun the export."
        )
    if not parent.is_dir():
        raise click.ClickException(f"Export parent path is not a directory: {parent}")


def _write_voice_logs_export(
    *,
    events: list[dict[str, Any]],
    path: Path,
    output_format: str,
) -> None:
    _validate_voice_logs_export_path(path)
    if output_format == "json":
        content = json.dumps(events, indent=2, sort_keys=True) + "\n"
    else:
        content = "".join(
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            for event in events
        )
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Could not write voice log export: {exc}") from exc


def _write_hammerspoon_bridge(path: Path, content: str) -> Path:
    path = path.expanduser()
    if "://" in str(path):
        raise click.ClickException("Hammerspoon bridge path must be local")
    if path.suffix.lower() != ".lua":
        raise click.ClickException("Hammerspoon bridge path must end in .lua")

    resolved_path = path.resolve(strict=False)
    active_init = (Path.home() / ".hammerspoon" / "init.lua").resolve(strict=False)
    if resolved_path == active_init:
        raise click.ClickException(
            "Refusing to modify the active ~/.hammerspoon/init.lua; "
            "write an example file elsewhere and install it manually"
        )
    if path.exists() and path.is_dir():
        raise click.ClickException(f"Hammerspoon bridge path is a directory: {path}")
    if path.exists() or path.is_symlink():
        raise click.ClickException(f"Hammerspoon bridge path already exists: {path}")
    if not path.parent.exists():
        raise click.ClickException(
            f"Hammerspoon bridge parent directory does not exist: {path.parent}. "
            "Create it first, then rerun the command."
        )
    if not path.parent.is_dir():
        raise click.ClickException(
            f"Hammerspoon bridge parent path is not a directory: {path.parent}"
        )

    try:
        with path.open("x", encoding="utf-8") as bridge_file:
            bridge_file.write(content)
    except OSError as exc:
        raise click.ClickException(
            f"Could not write Hammerspoon bridge: {exc}"
        ) from exc
    return path


def _validate_hammerspoon_bridge_file(path: Path) -> Path:
    path = path.expanduser()
    if "://" in str(path):
        raise click.ClickException("Hammerspoon bridge path must be local")
    if path.suffix.lower() != ".lua":
        raise click.ClickException("Hammerspoon bridge path must end in .lua")

    resolved_path = path.resolve(strict=False)
    active_init = (Path.home() / ".hammerspoon" / "init.lua").resolve(strict=False)
    if resolved_path == active_init:
        raise click.ClickException(
            "Refusing to validate the active ~/.hammerspoon/init.lua; "
            "validate a generated example file elsewhere"
        )
    if not path.exists():
        raise click.ClickException(f"Hammerspoon bridge path does not exist: {path}")
    if not path.is_file():
        raise click.ClickException(f"Hammerspoon bridge path is not a file: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise click.ClickException(f"Could not read Hammerspoon bridge: {exc}") from exc

    result = validate_hammerspoon_bridge(content)
    if not result.valid:
        details = "\n".join(f"  - {error}" for error in result.errors)
        raise click.ClickException(f"Hammerspoon bridge validation failed:\n{details}")
    return path


def _format_hammerspoon_install_preview(path: Path) -> None:
    resolved_path = path.resolve(strict=True)
    init_path = Path.home() / ".hammerspoon" / "init.lua"
    dofile_line = f"dofile({json.dumps(str(resolved_path))})"

    click.echo("Hammerspoon bridge install preview (no changes made)")
    click.echo(f"  bridge: {resolved_path}")
    click.echo("  validation: passed")
    click.echo("  generated bridge: disabled/preview-only by default")
    click.echo("  manual activation: user-performed outside Jarvis")
    click.echo("  active command: preview-only `jarvis voice hotkey-runtime --trigger`")
    click.echo("  approved dispatch: manual opt-in only")
    click.echo("  result speech: manual opt-in only")
    click.echo("  listener startup: not started")
    click.echo("  global hotkey capture: not enabled")
    click.echo("  ~/.hammerspoon/init.lua: not modified")
    click.echo("  files copied: none")
    click.echo("  Hammerspoon install: not attempted")
    click.echo("  Accessibility permission: not requested")
    click.echo("")
    click.echo("Manual install steps:")
    click.echo("  1. Install Hammerspoon yourself if you choose to use it.")
    click.echo(f"  2. Open {init_path} in an editor.")
    click.echo("  3. Add this line manually:")
    click.echo(f"     {dofile_line}")
    click.echo("  4. Save the file and reload Hammerspoon manually.")
    click.echo(
        "  5. Leave `enable_openjarvis_voice_hotkey = false` until you "
        "explicitly decide to enable capture."
    )
    click.echo(
        "  6. If enabling later, grant Accessibility permission manually in "
        "System Settings > Privacy & Security > Accessibility."
    )
    click.echo("")
    click.echo("Manual opt-in variants:")
    click.echo(
        "  - Approved dispatch requires manually choosing the commented "
        "`--approve-dispatch` command variant."
    )
    click.echo(
        "  - Result speech requires manually choosing the commented "
        "`--approve-dispatch --speak-result` command variant."
    )


def _format_hammerspoon_activation_guide(path: Path) -> None:
    resolved_path = path.resolve(strict=True)
    init_path = Path.home() / ".hammerspoon" / "init.lua"
    dofile_line = f"dofile({json.dumps(str(resolved_path))})"
    status = _hammerspoon_bridge_status(path)
    active_init = status["active_init"]
    app_status = status["hammerspoon_app"]

    click.echo("Hammerspoon push-to-talk activation guide (manual only)")
    click.echo(f"  bridge: {resolved_path}")
    click.echo("  validation: passed")
    click.echo("  activation owner: user, outside Jarvis")
    click.echo("  manual activation: user-performed outside Jarvis")
    click.echo(
        "  default behavior: preview-only `jarvis voice hotkey-runtime --trigger`"
    )
    click.echo("  approved dispatch: disabled unless manually opted in")
    click.echo("  result speech: disabled unless manually opted in")
    click.echo("")
    click.echo("Preflight checklist:")
    click.echo(f"  - bridge file exists: {status['file_exists']}")
    click.echo(f"  - bridge file is regular file: {status['file_is_file']}")
    click.echo("  - static validation passed: True")
    click.echo(
        f"  - preview-only default detected: {status['preview_only_default_detected']}"
    )
    click.echo("  - Lua execution by Jarvis: not attempted")
    click.echo("  - shell commands from bridge by Jarvis: not run")
    click.echo("  - listener started by Jarvis: False")
    click.echo("  - files modified by Jarvis: False")
    click.echo("  - ~/.hammerspoon/init.lua modified by Jarvis: False")
    click.echo("  - Hammerspoon installed by Jarvis: False")
    click.echo("  - Accessibility permission requested by Jarvis: False")
    click.echo("  - approval bypassed by Jarvis: False")
    click.echo("  - automatic dispatch by default: False")
    click.echo("  - automatic speech by default: False")
    click.echo(f"  - active init path: {active_init['path']}")
    click.echo(
        "  - active init currently references bridge: "
        f"{active_init['reference_detected']}"
    )
    if app_status["checked"]:
        click.echo(f"  - Hammerspoon app detected: {app_status['detected']}")
    else:
        click.echo(
            f"  - Hammerspoon app detected: not checked ({app_status['reason']})"
        )
    click.echo("")
    click.echo("Manual install steps:")
    click.echo("  1. Install Hammerspoon yourself if you choose to use it.")
    click.echo(f"  2. Open {init_path} in an editor.")
    click.echo("  3. Add this exact line manually:")
    click.echo(f"     {dofile_line}")
    click.echo("  4. Save the file and reload Hammerspoon manually.")
    click.echo(
        "  5. Keep `enable_openjarvis_voice_hotkey = false` to preserve "
        "preview-only behavior."
    )
    click.echo(
        "  6. To activate later, manually change "
        "`enable_openjarvis_voice_hotkey` to true in the bridge file."
    )
    click.echo(
        "  7. If macOS prompts or blocks the hotkey, grant Accessibility "
        "permission manually in System Settings > Privacy & Security > "
        "Accessibility."
    )
    click.echo("")
    click.echo("Manual rollback steps:")
    click.echo(
        "  1. Change `enable_openjarvis_voice_hotkey` back to false in the bridge file."
    )
    click.echo(f"  2. Remove this exact line from {init_path}:")
    click.echo(f"     {dofile_line}")
    click.echo("  3. Save the file and reload Hammerspoon manually.")
    click.echo(
        "  4. Optionally remove Hammerspoon's Accessibility permission manually "
        "in System Settings."
    )
    click.echo(
        "  5. Optionally delete the bridge file manually after it is no longer used."
    )
    click.echo("")
    click.echo(
        "Jarvis does not perform activation, rollback, permission changes, "
        "listener startup, dispatch, or speech from this guide."
    )


def _format_hammerspoon_rollback_guide(path: Path) -> None:
    expanded_path = path.expanduser()
    resolved_path = expanded_path.resolve(strict=False)
    init_path = Path.home() / ".hammerspoon" / "init.lua"
    active_init = init_path.resolve(strict=False)
    if resolved_path == active_init:
        raise click.ClickException(
            "Refusing to inspect the active ~/.hammerspoon/init.lua; "
            "use a generated bridge file path for rollback guidance"
        )
    dofile_line = f"dofile({json.dumps(str(resolved_path))})"
    exists = expanded_path.exists()
    is_file = expanded_path.is_file() if exists else False
    validation_errors: tuple[str, ...] = ()

    if exists and is_file:
        try:
            content = expanded_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            validation_errors = (f"could not read bridge file: {exc}",)
        else:
            validation_errors = validate_hammerspoon_bridge(content).errors
    elif exists:
        validation_errors = ("bridge path is not a file",)

    validation_status = (
        "passed"
        if exists and is_file and not validation_errors
        else ("not run; bridge file is missing" if not exists else "failed")
    )

    click.echo("Hammerspoon bridge rollback guide (manual only)")
    click.echo(f"  bridge: {resolved_path}")
    click.echo(f"  bridge file exists: {exists}")
    click.echo(f"  bridge file is regular file: {is_file}")
    click.echo(f"  static validation: {validation_status}")
    click.echo(
        "  preview-only default: restored by setting "
        "`enable_openjarvis_voice_hotkey = false` manually"
    )
    click.echo("  manual activation: not performed by Jarvis")
    if validation_errors:
        click.echo("  validation errors:")
        for error in validation_errors:
            click.echo(f"    - {error}")
    click.echo("  no files were changed")
    click.echo("  no listener was started")
    click.echo("  Lua execution by Jarvis: not attempted")
    click.echo("  shell commands from bridge by Jarvis: not run")
    click.echo("  ~/.hammerspoon/init.lua modified by Jarvis: False")
    click.echo("  Hammerspoon installed by Jarvis: False")
    click.echo("  Accessibility permission requested by Jarvis: False")
    click.echo("  approval bypassed by Jarvis: False")
    click.echo("  automatic dispatch by default: False")
    click.echo("  automatic speech by default: False")
    click.echo("")
    click.echo("Manual backup steps:")
    click.echo(
        f"  1. Open {init_path} in an editor and confirm it is your active config."
    )
    click.echo("  2. Before editing, make a manual backup yourself. Example:")
    click.echo(
        "     cp ~/.hammerspoon/init.lua ~/.hammerspoon/init.lua.openjarvis-backup"
    )
    click.echo(
        "  3. If ~/.hammerspoon/init.lua does not exist, there is no active init "
        "file to back up."
    )
    click.echo("")
    click.echo("Manual rollback steps:")
    click.echo("  1. In the bridge file, set this line back to false if it exists:")
    click.echo("     local enable_openjarvis_voice_hotkey = false")
    click.echo(f"  2. Remove this exact line manually from {init_path}:")
    click.echo(f"     {dofile_line}")
    click.echo("  3. Save ~/.hammerspoon/init.lua.")
    click.echo("  4. Reload Hammerspoon manually from the Hammerspoon menu bar icon:")
    click.echo("     Hammerspoon > Reload Config")
    click.echo(
        "  5. Optionally remove Hammerspoon's Accessibility permission manually "
        "in System Settings > Privacy & Security > Accessibility."
    )
    click.echo("  6. Optionally delete the bridge file manually after rollback.")
    click.echo("")
    click.echo(
        "Jarvis did not modify files, start a listener, execute Lua, run bridge "
        "shell commands, install Hammerspoon, request Accessibility permission, "
        "dispatch, or speak."
    )


def _active_init_references_bridge(init_path: Path, bridge_path: Path) -> bool:
    if not init_path.exists() or not init_path.is_file():
        return False
    try:
        init_content = init_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False

    resolved_bridge = bridge_path.expanduser().resolve(strict=False)
    expanded_bridge = bridge_path.expanduser()
    candidates = {str(resolved_bridge), str(expanded_bridge)}
    return any(candidate and candidate in init_content for candidate in candidates)


def _hammerspoon_app_status() -> dict[str, Any]:
    if sys.platform != "darwin":
        return {
            "checked": False,
            "detected": False,
            "paths": [],
            "reason": "not macOS",
        }

    candidate_paths = [
        Path("/Applications/Hammerspoon.app"),
        Path.home() / "Applications" / "Hammerspoon.app",
    ]
    detected_paths = [str(path) for path in candidate_paths if path.exists()]
    return {
        "checked": True,
        "detected": bool(detected_paths),
        "paths": detected_paths,
        "reason": "filesystem check only",
    }


def _hammerspoon_bridge_status(path: Path) -> dict[str, Any]:
    expanded_path = path.expanduser()
    resolved_path = expanded_path.resolve(strict=False)
    active_init = Path.home() / ".hammerspoon" / "init.lua"
    exists = expanded_path.exists()
    is_file = expanded_path.is_file() if exists else False
    validation_errors: tuple[str, ...]

    if exists and is_file:
        try:
            content = expanded_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            validation_errors = (f"could not read bridge file: {exc}",)
        else:
            validation = validate_hammerspoon_bridge(content)
            validation_errors = validation.errors
    elif exists:
        validation_errors = ("bridge path is not a file",)
    else:
        validation_errors = ("bridge file does not exist",)

    valid = not validation_errors
    readiness_state = "ready_for_manual_review" if valid else "not_ready"
    next_step = (
        "Review the disabled bridge and use --install-preview for manual steps."
        if valid
        else "Fix validation errors before any manual install preview."
    )
    return {
        "bridge": str(resolved_path),
        "file_exists": exists,
        "file_is_file": is_file,
        "valid": valid,
        "validation_errors": list(validation_errors),
        "preview_only_default_detected": valid,
        "active_init": {
            "path": str(active_init),
            "exists": active_init.exists(),
            "reference_detected": _active_init_references_bridge(
                active_init,
                expanded_path,
            ),
        },
        "hammerspoon_app": _hammerspoon_app_status(),
        "readiness": {
            "state": readiness_state,
            "next_safe_manual_step": next_step,
            "activation_deferred": True,
            "global_hotkey_enabled": False,
        },
        "safety": {
            "listener_started": False,
            "files_modified": False,
            "lua_executed": False,
            "bridge_shell_commands_run": False,
            "init_modified": False,
            "hammerspoon_installed": False,
            "accessibility_permission_requested": False,
            "microphone_permission_requested": False,
            "dispatch_started": False,
            "speech_started": False,
        },
    }


def _manual_hotkey_activation_checklist(
    data: dict[str, Any],
    voice_setup: dict[str, Any],
) -> dict[str, Any]:
    recorder = voice_setup["recorder"]
    adapter = voice_setup["transcription_adapter"]
    model = voice_setup["model_path"]
    safety = data["safety"]
    active_init = data["active_init"]
    app_status = data["hammerspoon_app"]

    local_adapter_configured = (
        bool(adapter["effective"])
        and adapter["effective"] != "disabled"
        and adapter["supported"] is True
    )
    model_configured = bool(model["value"]) and model["exists"] is not False
    real_recorder_configured = recorder["real_microphone_recorder_configured"] is True
    dispatch_disabled = safety["dispatch_started"] is False
    speech_disabled = safety["speech_started"] is False

    return {
        "bridge_file_generated": data["file_exists"] and data["file_is_file"],
        "bridge_validates_safely": data["valid"],
        "preview_only_default": data["preview_only_default_detected"],
        "real_mic_recorder_configured": real_recorder_configured,
        "local_transcription_adapter_model_configured": (
            local_adapter_configured and model_configured
        ),
        "approval_required": voice_setup["approval"]["required"] is True,
        "dispatch_disabled_unless_explicit": dispatch_disabled,
        "speech_disabled_unless_explicit": speech_disabled,
        "hammerspoon_detection_safely_checkable": app_status["checked"],
        "hammerspoon_detected": app_status["detected"],
        "hammerspoon_detection_note": app_status["reason"],
        "active_init_reference_detected": active_init["reference_detected"],
        "accessibility_permission_user_managed": True,
        "microphone_permission_user_managed": True,
        "manual_install_guide_available": data["valid"],
        "rollback_guide_available": True,
        "ready_for_manual_review": (
            data["file_exists"]
            and data["file_is_file"]
            and data["valid"]
            and data["preview_only_default_detected"]
            and real_recorder_configured
            and local_adapter_configured
            and model_configured
            and voice_setup["approval"]["required"] is True
            and dispatch_disabled
            and speech_disabled
        ),
    }


def _format_hammerspoon_bridge_status(data: dict[str, Any]) -> None:
    click.echo("Hammerspoon bridge status (read-only)")
    click.echo(f"  bridge: {data['bridge']}")
    click.echo(f"  file exists: {data['file_exists']}")
    click.echo(
        "  validation: "
        f"{'passed' if data['valid'] else 'failed'} "
        "(Phase 6 static validator)"
    )
    if data["validation_errors"]:
        click.echo("  validation errors:")
        for error in data["validation_errors"]:
            click.echo(f"    - {error}")
    click.echo(
        f"  preview-only default detected: {data['preview_only_default_detected']}"
    )
    readiness = data["readiness"]
    click.echo(f"  readiness: {readiness['state']}")
    click.echo(f"  next safe manual step: {readiness['next_safe_manual_step']}")
    click.echo(f"  activation deferred: {readiness['activation_deferred']}")
    click.echo(f"  global hotkey enabled: {readiness['global_hotkey_enabled']}")
    active_init = data["active_init"]
    click.echo(f"  active init: {active_init['path']}")
    click.echo(f"  active init reference detected: {active_init['reference_detected']}")
    click.echo(
        f"  manual install reference present: {active_init['reference_detected']}"
    )
    app_status = data["hammerspoon_app"]
    if app_status["checked"]:
        click.echo(f"  Hammerspoon app detected: {app_status['detected']}")
        if app_status["paths"]:
            click.echo(f"  Hammerspoon app paths: {', '.join(app_status['paths'])}")
    else:
        click.echo(f"  Hammerspoon app detected: not checked ({app_status['reason']})")
    safety = data["safety"]
    click.echo(f"  no listener was started: {not safety['listener_started']}")
    click.echo(f"  no files were modified: {not safety['files_modified']}")
    lua_status = "not attempted" if not safety["lua_executed"] else "attempted"
    click.echo(f"  Lua execution: {lua_status}")
    click.echo(
        "  shell commands from bridge: "
        f"{'not run' if not safety['bridge_shell_commands_run'] else 'run'}"
    )
    click.echo(f"  ~/.hammerspoon/init.lua modified: {safety['init_modified']}")
    click.echo(
        "  Hammerspoon install: "
        f"{'not attempted' if not safety['hammerspoon_installed'] else 'attempted'}"
    )
    accessibility_status = (
        "not requested"
        if not safety["accessibility_permission_requested"]
        else "requested"
    )
    click.echo(f"  Accessibility permission: {accessibility_status}")
    click.echo(f"  dispatch started: {safety['dispatch_started']}")
    click.echo(f"  speech started: {safety['speech_started']}")


def _format_hammerspoon_activation_status(data: dict[str, Any]) -> None:
    checklist = data["manual_activation_checklist"]
    click.echo("Hammerspoon bridge activation readiness (manual only)")
    click.echo(f"  bridge: {data['bridge']}")
    click.echo(
        f"  generated bridge exists: {data['file_exists'] and data['file_is_file']}"
    )
    click.echo(f"  bridge validates safely: {data['valid']}")
    if data["validation_errors"]:
        click.echo("  validation errors:")
        for error in data["validation_errors"]:
            click.echo(f"    - {error}")
    click.echo(f"  preview-only default: {data['preview_only_default_detected']}")
    click.echo(f"  manual install guide available: {data['valid']}")
    click.echo("  manual rollback guide available: True")
    click.echo("")
    click.echo("Final manual hotkey activation safety checklist:")
    click.echo(f"  - bridge file generated: {checklist['bridge_file_generated']}")
    click.echo(f"  - bridge validates safely: {checklist['bridge_validates_safely']}")
    click.echo(f"  - preview-only default: {checklist['preview_only_default']}")
    click.echo(
        f"  - real mic recorder configured: {checklist['real_mic_recorder_configured']}"
    )
    click.echo(
        "  - local transcription adapter/model configured: "
        f"{checklist['local_transcription_adapter_model_configured']}"
    )
    click.echo(f"  - approval required: {checklist['approval_required']}")
    click.echo(
        "  - dispatch disabled unless explicit: "
        f"{checklist['dispatch_disabled_unless_explicit']}"
    )
    click.echo(
        "  - speech disabled unless explicit: "
        f"{checklist['speech_disabled_unless_explicit']}"
    )
    if checklist["hammerspoon_detection_safely_checkable"]:
        click.echo(
            "  - Hammerspoon installed/detected if safely checkable: "
            f"{checklist['hammerspoon_detected']}"
        )
    else:
        click.echo(
            "  - Hammerspoon installed/detected if safely checkable: "
            f"not checked ({checklist['hammerspoon_detection_note']})"
        )
    click.echo(
        "  - active init.lua reference detected: "
        f"{checklist['active_init_reference_detected']}"
    )
    click.echo(
        "  - Accessibility permission is user-managed: "
        f"{checklist['accessibility_permission_user_managed']}"
    )
    click.echo(
        "  - Microphone permission is user-managed: "
        f"{checklist['microphone_permission_user_managed']}"
    )
    click.echo(f"  - rollback guide available: {checklist['rollback_guide_available']}")
    click.echo(f"  - ready for manual review: {checklist['ready_for_manual_review']}")
    active_init = data["active_init"]
    click.echo(f"  active init: {active_init['path']}")
    click.echo(f"  active init reference detected: {active_init['reference_detected']}")
    app_status = data["hammerspoon_app"]
    click.echo(f"  Hammerspoon app detected: {app_status['detected']}")
    if app_status["paths"]:
        click.echo(f"  Hammerspoon app paths: {', '.join(app_status['paths'])}")
    elif app_status["reason"]:
        click.echo(f"  Hammerspoon app detection note: {app_status['reason']}")
    safety = data["safety"]
    click.echo("  Accessibility permission: user-managed; not requested by Jarvis")
    click.echo("  Microphone permission: user-managed; not requested by Jarvis")
    click.echo(
        f"  global listener not started by Jarvis: {not safety['listener_started']}"
    )
    click.echo("  activation: deferred/manual")
    click.echo("  manual activation: user-performed outside Jarvis")
    lua_status = "attempted" if safety["lua_executed"] else "not attempted"
    click.echo(f"  Lua execution by Jarvis: {lua_status}")
    click.echo(
        "  shell commands from bridge by Jarvis: "
        f"{'run' if safety['bridge_shell_commands_run'] else 'not run'}"
    )
    click.echo(f"  files modified by Jarvis: {safety['files_modified']}")
    click.echo(
        f"  ~/.hammerspoon/init.lua modified by Jarvis: {safety['init_modified']}"
    )
    click.echo(f"  Hammerspoon installed by Jarvis: {safety['hammerspoon_installed']}")
    click.echo("  approval bypassed by Jarvis: False")
    click.echo(f"  automatic dispatch by default: {safety['dispatch_started']}")
    click.echo(f"  automatic speech by default: {safety['speech_started']}")
    click.echo(
        "  Jarvis does not activate the bridge, request permissions, dispatch, "
        "or speak from this status command."
    )


def _parse_voice_logs_clear_before(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise click.UsageError("--clear-before must use YYYY-MM-DD format") from exc


def _voice_event_logger() -> VoiceEventLogger:
    return VoiceEventLogger(voice_log_settings_from_config(load_config()))


def _log_voice_event(
    command: str,
    event: str,
    *,
    status: str = "ok",
    transcript: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    _voice_event_logger().record(
        command=command,
        event=event,
        status=status,
        transcript=transcript,
        details=details,
    )


def _preview_log_details(data: dict[str, Any]) -> dict[str, Any]:
    preview = data.get("intent_preview") or {}
    return {
        "preview_status": data.get("status", ""),
        "fsm_state": data.get("fsm_state", ""),
        "intent": preview.get("interpreted_intent", ""),
        "risk_level": preview.get("risk_level", ""),
        "approval_required": bool(preview.get("approval_required", False)),
        "approved": bool(data.get("approved", False)),
        "dispatched": bool(data.get("dispatched", False)),
    }


def _dispatch_log_details(
    data: dict[str, Any],
    *,
    approved: bool,
    agent_id: str,
) -> dict[str, Any]:
    return {
        "approved": approved,
        "agent_id": agent_id,
        "dispatched": bool(data.get("dispatched", False)),
        "dispatch_status": data.get("status", ""),
        "fsm_state": data.get("fsm_state", ""),
        "reason": data.get("reason", ""),
        "has_error": bool(data.get("error")),
    }


def _format_preview(data: dict[str, Any]) -> None:
    preview = data.get("intent_preview") or {}
    click.echo("Voice transcript preview")
    click.echo(f"  status: {data.get('status', '-')}")
    click.echo(f"  fsm_state: {data.get('fsm_state', '-')}")
    click.echo(f"  intent: {preview.get('interpreted_intent', '-')}")
    click.echo(f"  risk: {preview.get('risk_level', '-')}")
    click.echo(f"  approval_required: {preview.get('approval_required', False)}")

    planned_actions = preview.get("planned_actions") or []
    if planned_actions:
        click.echo("  planned_actions:")
        for action in planned_actions:
            click.echo(f"    - {action}")


def _format_dispatch(data: dict[str, Any]) -> None:
    click.echo("Voice dispatch result")
    click.echo(f"  dispatched: {data.get('dispatched', False)}")
    click.echo(f"  fsm_state: {data.get('fsm_state', '-')}")
    if data.get("agent_id"):
        click.echo(f"  agent_id: {data['agent_id']}")
    if data.get("status"):
        click.echo(f"  status: {data['status']}")
    if data.get("reason"):
        click.echo(f"  reason: {data['reason']}")
    if data.get("error"):
        click.echo(f"  error: {data['error']}")


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _build_recorder(
    recorder_kind: str,
    *,
    output_dir: Path | None,
    input_device: str,
) -> Recorder:
    if recorder_kind == "macos":
        return LocalMacOSRecorder(temp_dir=output_dir, input_device=input_device)
    if recorder_kind == "sounddevice":
        device = None if input_device == ":0" else input_device
        return SoundDeviceRecorder(temp_dir=output_dir, input_device=device)
    return SilentWavRecorder(temp_dir=output_dir)


def _configured_recorder_kind(recorder_kind: str | None) -> str:
    if recorder_kind:
        return recorder_kind
    voice_control = _voice_control_config(load_config())
    configured = str(getattr(voice_control, "default_recorder", "") or "dev-silent")
    if configured not in RECORDER_KINDS:
        raise click.ClickException(
            f"unsupported local recorder configured in "
            f"[voice_control].default_recorder: {configured}"
        )
    return configured


def _configured_microphone_recorder_kind(recorder_kind: str | None) -> str:
    configured = _configured_recorder_kind(recorder_kind)
    if configured not in MICROPHONE_RECORDER_KINDS:
        raise click.ClickException(
            "This microphone command requires a real microphone recorder. Pass "
            "--recorder "
            "macos or --recorder sounddevice, or configure one in "
            "[voice_control].default_recorder."
        )
    return configured


def _configured_hotkey_microphone_recorder_kind(recorder_kind: str | None) -> str:
    if recorder_kind:
        configured = recorder_kind
    else:
        voice_control = _voice_control_config(load_config())
        configured = str(
            getattr(voice_control, "hotkey_bridge_recorder", "") or "macos"
        )
    if configured not in MICROPHONE_RECORDER_KINDS:
        raise click.ClickException(
            "The hotkey runtime trigger requires a real microphone recorder. Pass "
            "--recorder macos or --recorder sounddevice, or configure "
            "[voice_control].hotkey_bridge_recorder."
        )
    return configured


def _configured_hotkey_input_device(input_device: str | None) -> str:
    if input_device:
        return input_device
    voice_control = _voice_control_config(load_config())
    return str(getattr(voice_control, "hotkey_bridge_input_device", ":0") or ":0")


def _configured_hotkey_session_id(session_id: str) -> str:
    if session_id:
        return session_id
    voice_control = _voice_control_config(load_config())
    return str(getattr(voice_control, "hotkey_bridge_session_id", "") or "")


def _validate_real_microphone_duration(
    recorder_kind: str,
    duration: float,
) -> None:
    if (
        recorder_kind in MICROPHONE_RECORDER_KINDS
        and duration > MICROPHONE_MAX_DURATION_SECONDS
    ):
        raise click.UsageError(
            "Real microphone recording duration must be between "
            f"{MICROPHONE_MIN_DURATION_SECONDS:g} and "
            f"{MICROPHONE_MAX_DURATION_SECONDS:g} seconds."
        )


def _validate_bounded_microphone_duration(duration: float) -> None:
    if not (
        MICROPHONE_MIN_DURATION_SECONDS <= duration <= MICROPHONE_MAX_DURATION_SECONDS
    ):
        raise click.UsageError(
            "Microphone recording duration must be between "
            f"{MICROPHONE_MIN_DURATION_SECONDS:g} and "
            f"{MICROPHONE_MAX_DURATION_SECONDS:g} seconds."
        )


def _voice_control_config(config: Any) -> Any:
    return getattr(config, "voice_control", None)


def _configured_transcription_adapter(
    adapter: str | None,
    *,
    config: Any,
) -> str | None:
    if adapter:
        return adapter
    voice_control = _voice_control_config(config)
    configured = getattr(voice_control, "transcription_adapter", "")
    return str(configured) if configured else None


def _effective_voice_config(config: Any) -> Any:
    voice_control = _voice_control_config(config)
    model_path = getattr(voice_control, "model_path", "")
    if not model_path:
        return config

    try:
        speech = replace(config.speech, model=str(model_path))
        return replace(config, speech=speech)
    except (AttributeError, TypeError, ValueError):
        if hasattr(config, "speech"):
            setattr(config.speech, "model", str(model_path))
        return config


def _record_duration(duration: float | None) -> float:
    if duration is not None:
        return duration

    config = load_config()
    voice_control = _voice_control_config(config)
    raw_configured = getattr(voice_control, "default_record_duration", 0.0) or 0.0
    try:
        configured = float(raw_configured)
    except (TypeError, ValueError) as exc:
        raise click.ClickException(
            "[voice_control].default_record_duration must be a positive number"
        ) from exc
    if configured > 0:
        return configured
    raise click.UsageError(
        "Missing option '--duration'. Set --duration or "
        "[voice_control].default_record_duration."
    )


def _speech_output_adapter(adapter: str | None) -> str:
    if adapter:
        return adapter

    config = load_config()
    voice_control = _voice_control_config(config)
    configured = getattr(voice_control, "speech_output_adapter", "")
    if configured:
        if configured not in LOCAL_SPEECH_OUTPUT_ADAPTERS:
            raise click.ClickException(
                f"unsupported local speech-output adapter: {configured}"
            )
        return str(configured)
    return "macos-say"


def _speech_voice(voice_name: str | None) -> str:
    if voice_name:
        return voice_name
    voice_control = _voice_control_config(load_config())
    return str(getattr(voice_control, "speech_voice", "") or "")


def _speech_rate(rate: int | None) -> int | None:
    if rate is not None:
        return rate
    voice_control = _voice_control_config(load_config())
    raw_configured = getattr(voice_control, "speech_rate", 0) or 0
    try:
        configured = int(raw_configured)
    except (TypeError, ValueError) as exc:
        raise click.ClickException(
            "[voice_control].speech_rate must be a positive integer"
        ) from exc
    return configured if configured > 0 else None


def _hotkey_bridge_defaults() -> Any:
    return _voice_control_config(load_config())


def _build_transcriber(
    adapter: str | None,
) -> tuple[str, SpeechBackendLocalTranscriptionAdapter]:
    raw_config = load_config()
    config = _effective_voice_config(raw_config)
    requested_adapter = _configured_transcription_adapter(adapter, config=raw_config)
    try:
        adapter_id = resolve_local_transcription_adapter_id(
            requested_adapter=requested_adapter,
            config=config,
        )
    except (ValueError, TranscriptionUnavailableError) as exc:
        raise click.ClickException(str(exc)) from exc
    return (
        adapter_id,
        SpeechBackendLocalTranscriptionAdapter(
            adapter_id=adapter_id,
            config=config,
        ),
    )


def _transcribe_audio_file(
    audio_file: Path,
    *,
    adapter: str | None,
    language: str | None,
) -> dict[str, Any]:
    _, transcriber = _build_transcriber(adapter)
    try:
        result = transcriber.transcribe_file(audio_file, language=language)
    except (OSError, TranscriptionUnavailableError) as exc:
        raise click.ClickException(str(exc)) from exc
    return result.to_dict()


def _record_local_audio(
    *,
    duration: float,
    output_dir: Path | None,
    recorder_kind: str,
    input_device: str,
    cleanup_on_error: bool = False,
) -> Any:
    recorder = _build_recorder(
        recorder_kind,
        output_dir=output_dir,
        input_device=input_device,
    )
    try:
        handle = recorder.start(uuid.uuid4().hex)
    except (OSError, VoiceRecordingError) as exc:
        raise click.ClickException(str(exc)) from exc
    stop_error: OSError | VoiceRecordingError | None = None
    try:
        _sleep(duration)
    finally:
        try:
            recorder.stop(handle)
        except (OSError, VoiceRecordingError) as exc:
            stop_error = exc
    if stop_error is not None:
        if cleanup_on_error:
            try:
                handle.path.unlink(missing_ok=True)
            except OSError:
                pass
        raise click.ClickException(str(stop_error)) from stop_error
    return handle


def _build_speech_output(
    adapter_id: str,
    *,
    voice_name: str,
    rate: int | None,
) -> LocalSpeechOutput:
    try:
        return build_local_speech_output(adapter_id, voice=voice_name, rate=rate)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _dispatch_speech_text(data: dict[str, Any]) -> str:
    content = data.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    if content is not None:
        return json.dumps(content, sort_keys=True)
    if data.get("reason"):
        return str(data["reason"])
    error = data.get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    if data.get("status"):
        return str(data["status"])
    raise click.ClickException("dispatch result did not include speakable content")


def _configured_api_base_url(config: Any) -> dict[str, str]:
    voice_control = _voice_control_config(config)
    configured_base = getattr(voice_control, "default_api_base_url", "")
    if configured_base:
        return {
            "value": str(configured_base).rstrip("/"),
            "source": "[voice_control].default_api_base_url",
        }

    host = config.server.host
    if host in {"0.0.0.0", "::", ""}:
        host = "127.0.0.1"
    return {
        "value": f"http://{host}:{config.server.port}",
        "source": "[server].host/[server].port",
    }


def _looks_like_path(value: str) -> bool:
    return (
        "/" in value or "\\" in value or value.startswith(".") or value.startswith("~")
    )


def _voice_doctor_model_path(config: Any, adapter_id: str) -> dict[str, Any]:
    voice_control = _voice_control_config(config)
    configured_model = str(getattr(voice_control, "model_path", "") or "")
    if configured_model:
        path_required = _looks_like_path(configured_model)
        path_exists = (
            Path(configured_model).expanduser().exists() if path_required else None
        )
        return {
            "value": configured_model,
            "source": "[voice_control].model_path",
            "required": path_required,
            "exists": path_exists,
        }

    if adapter_id == "whisper.cpp":
        whisper_model = os.environ.get("WHISPER_CPP_MODEL", "")
        return {
            "value": whisper_model,
            "source": "WHISPER_CPP_MODEL" if whisper_model else "",
            "required": True,
            "exists": Path(whisper_model).expanduser().exists()
            if whisper_model
            else False,
        }

    return {
        "value": str(getattr(config.speech, "model", "") or ""),
        "source": "[speech].model",
        "required": False,
        "exists": None,
    }


def _voice_doctor_data() -> dict[str, Any]:
    config = load_config()
    voice_control = _voice_control_config(config)

    configured_adapter = str(getattr(voice_control, "transcription_adapter", "") or "")
    speech_backend = str(getattr(config.speech, "backend", "") or "")
    if configured_adapter:
        effective_adapter = configured_adapter
        adapter_source = "[voice_control].transcription_adapter"
    elif speech_backend in LOCAL_TRANSCRIPTION_ADAPTERS:
        effective_adapter = speech_backend
        adapter_source = "[speech].backend"
    else:
        effective_adapter = "disabled"
        adapter_source = ""

    raw_duration = getattr(voice_control, "default_record_duration", 0.0) or 0.0
    try:
        configured_duration = float(raw_duration)
    except (TypeError, ValueError):
        configured_duration = 0.0

    configured_recorder = str(
        getattr(voice_control, "default_recorder", "") or "dev-silent"
    )
    speech_adapter = str(getattr(voice_control, "speech_output_adapter", "") or "")
    effective_speech_adapter = speech_adapter or "macos-say"
    say_path = shutil.which("say")
    say_relevant = effective_speech_adapter == "macos-say"

    return {
        "api_base_url": _configured_api_base_url(config),
        "transcription_adapter": {
            "configured": configured_adapter,
            "effective": effective_adapter,
            "source": adapter_source,
            "supported": effective_adapter in LOCAL_TRANSCRIPTION_ADAPTERS,
        },
        "model_path": _voice_doctor_model_path(config, effective_adapter),
        "record_duration": {
            "configured_default_seconds": configured_duration,
            "effective_default_seconds": configured_duration
            if configured_duration > 0
            else None,
            "duration_flag_required": configured_duration <= 0,
        },
        "recording_policy": microphone_recording_policy(),
        "recorder": recorder_diagnostics(configured_recorder),
        "speech_output": {
            "configured": speech_adapter,
            "effective": effective_speech_adapter,
            "supported": effective_speech_adapter in LOCAL_SPEECH_OUTPUT_ADAPTERS,
        },
        "macos_say": {
            "relevant": say_relevant,
            "available": bool(say_path) and sys.platform == "darwin",
            "path": say_path or "",
        },
        "hotkey_bridge": {
            "configured_format": str(
                getattr(voice_control, "hotkey_bridge_format", "command") or "command"
            ),
            "print_only": True,
            "enabled": False,
            "listener_started": False,
            "global_key_capture": False,
        },
        "approval": {
            "required": bool(
                getattr(config.speech, "require_explicit_voice_approval", True)
            ),
            "config": "[speech].require_explicit_voice_approval",
        },
        "safety": {
            "microphone_access_required": False,
            "model_download_required": False,
            "dispatch_called": False,
            "speech_called": False,
            "hotkeys_started": False,
            "approval_bypassed": False,
        },
    }


def _format_voice_doctor(data: dict[str, Any]) -> None:
    click.echo("Voice doctor")
    click.echo(
        f"  api_base_url: {data['api_base_url']['value']} "
        f"({data['api_base_url']['source']})"
    )
    adapter = data["transcription_adapter"]
    click.echo(f"  transcription_adapter: {adapter['effective']}")
    model = data["model_path"]
    exists = model["exists"] if model["exists"] is not None else "not required"
    click.echo(
        f"  model_path: {model['value'] or '-'} "
        f"(required={model['required']}, exists={exists})"
    )
    duration = data["record_duration"]
    default_duration = duration["effective_default_seconds"]
    click.echo(
        "  record_duration: "
        f"{default_duration if default_duration is not None else 'requires --duration'}"
    )
    policy = data["recording_policy"]
    click.echo(
        "  microphone_duration_bounds: "
        f"{policy['minimum_duration_seconds']:g}-"
        f"{policy['maximum_duration_seconds']:g} seconds"
    )
    click.echo(
        "  temporary_wav_cleanup: deleted by default; retention requires --keep-file"
    )
    recorder = data["recorder"]
    click.echo(
        "  recorder: "
        f"{recorder['configured_default']} "
        f"(supported={recorder['supported']}, "
        f"available={recorder['backend_available']})"
    )
    click.echo(f"  sounddevice_importable: {recorder['sounddevice_importable']}")
    click.echo(
        f"  dev_silent_recorder_available: {recorder['dev_silent_recorder_available']}"
    )
    click.echo(
        "  microphone_recording_configured: "
        f"{recorder['microphone_recording_configured']}"
    )
    click.echo(
        "  microphone_configuration_ready: "
        f"{recorder['microphone_configuration_ready']} "
        "(permission not checked)"
    )
    click.echo(
        "  macos_microphone_permission: "
        f"{recorder['macos_microphone_permission_guidance']}"
    )
    speech_output = data["speech_output"]
    click.echo(f"  speech_output: {speech_output['effective']}")
    macos_say = data["macos_say"]
    if macos_say["relevant"]:
        click.echo(f"  macos_say_available: {macos_say['available']}")
    hotkey_bridge = data["hotkey_bridge"]
    click.echo(
        "  hotkey_bridge: "
        f"print_only={hotkey_bridge['print_only']}, enabled={hotkey_bridge['enabled']}"
    )
    click.echo(f"  approval_required: {data['approval']['required']}")
    click.echo(
        "  safety: no microphone, downloads, dispatch, speech, or hotkeys started"
    )


def _hotkey_runtime_contract_data() -> dict[str, Any]:
    return {
        "name": "OpenJarvis Hammerspoon push-to-talk runtime bridge contract",
        "version": 1,
        "state": {
            "enabled_by_default": False,
            "listener_started_by_python": False,
            "hammerspoon_init_modified": False,
            "hammerspoon_installed": False,
            "accessibility_permission_requested": False,
            "dispatches_by_default": False,
            "speaks_by_default": False,
        },
        "external_trigger": {
            "owner": "external Hammerspoon script, manually installed by the user",
            "shape": [
                "jarvis",
                "voice",
                "hotkey-runtime",
                "--trigger",
                "--duration",
                "SECONDS",
                "--recorder",
                "macos|sounddevice",
                "--adapter",
                "faster-whisper|whisper.cpp",
            ],
            "optional_flags": [
                "--input-device DEVICE",
                "--language LANGUAGE",
                "--base-url URL",
                "--session-id ID",
                "--keep-file",
            ],
            "forbidden_default_flags": [
                "--approve-dispatch",
                "--speak-result",
            ],
        },
        "default_command_path": {
            "command": (
                "jarvis voice hotkey-runtime --trigger --duration SECONDS "
                "--recorder macos --adapter faster-whisper"
            ),
            "internal_safe_path": "jarvis voice mic-run",
            "behavior": "preview-only",
            "submit_endpoint": "/v1/voice/ptt/submit-transcript",
            "dispatch_endpoint": "/v1/voice/ptt/dispatch",
            "dispatch_called_by_default": False,
        },
        "requirements": {
            "duration_seconds": {
                "required": True,
                "minimum": MICROPHONE_MIN_DURATION_SECONDS,
                "maximum": MICROPHONE_MAX_DURATION_SECONDS,
            },
            "recorder": {
                "required": True,
                "allowed": list(MICROPHONE_RECORDER_KINDS),
                "must_be_real_microphone_backend": True,
            },
            "transcription": {
                "required": True,
                "allowed_adapters": list(LOCAL_TRANSCRIPTION_ADAPTERS),
                "model": "explicit or configured local adapter/model only",
                "cloud_transcription_by_default": False,
            },
            "approval": {
                "required_for_dispatch": True,
                "opt_in_flag": "--approve-dispatch",
                "bypass_allowed": False,
            },
            "speech": {
                "allowed_only_after_approved_dispatch": True,
                "opt_in_flag": "--speak-result",
                "automatic": False,
            },
        },
        "exit_codes": {
            "0": "contract printed, or runtime preview/approved path completed",
            "1": "runtime/configuration/API/recording/transcription/speech error",
            "2": "CLI usage error such as missing duration or invalid flags",
        },
        "stdio": {
            "stdout": (
                "Human-readable preview/status by default; JSON only when an "
                "existing command explicitly supports --json. No raw audio is "
                "written to stdout."
            ),
            "stderr": (
                "Click usage errors and runtime errors. External helpers should "
                "treat stderr as diagnostic text, not as a transcript."
            ),
        },
        "event_logging": {
            "path": "[voice_control].voice_logs_path when local logging is enabled",
            "redaction": (
                "Transcript events store length/hash/redacted preview by default; "
                "full transcript logging requires explicit config opt-in."
            ),
            "raw_audio_logged": False,
            "contract_command_writes_event": False,
        },
        "rollback_safety": {
            "disable_external_capture": (
                "Set the external Hammerspoon guard back to false or remove the "
                "manual dofile(...) line from ~/.hammerspoon/init.lua."
            ),
            "jarvis_rollback_actions": "none; rollback remains user-managed",
            "safe_to_run_contract_repeatedly": True,
        },
    }


def _hotkey_runtime_dry_run_data() -> dict[str, Any]:
    config = load_config()
    voice_control = _voice_control_config(config)
    issues: list[str] = []
    guidance: list[str] = []

    raw_duration = getattr(voice_control, "default_record_duration", 0.0) or 0.0
    try:
        duration = float(raw_duration) or 2.0
    except (TypeError, ValueError):
        duration = 2.0
        issues.append("[voice_control].default_record_duration must be numeric")
        guidance.append(
            "Set [voice_control].default_record_duration to 0.1-30, or leave it "
            "at 0 to use the hotkey runtime dry-run fallback of 2.0 seconds."
        )
    if not (
        MICROPHONE_MIN_DURATION_SECONDS <= duration <= MICROPHONE_MAX_DURATION_SECONDS
    ):
        issues.append(
            "[voice_control].default_record_duration must be between "
            f"{MICROPHONE_MIN_DURATION_SECONDS:g} and "
            f"{MICROPHONE_MAX_DURATION_SECONDS:g} seconds"
        )
        guidance.append(
            "Use a bounded recording duration before wiring an external hotkey."
        )

    recorder = str(getattr(voice_control, "hotkey_bridge_recorder", "macos") or "macos")
    if recorder not in MICROPHONE_RECORDER_KINDS:
        issues.append(
            "[voice_control].hotkey_bridge_recorder must be macos or sounddevice"
        )
        guidance.append(
            "Set [voice_control].hotkey_bridge_recorder to a real microphone "
            "backend: macos or sounddevice."
        )

    configured_adapter = str(getattr(voice_control, "transcription_adapter", "") or "")
    speech_backend = str(getattr(config.speech, "backend", "") or "")
    if configured_adapter:
        adapter = configured_adapter
        adapter_source = "[voice_control].transcription_adapter"
    elif speech_backend in LOCAL_TRANSCRIPTION_ADAPTERS:
        adapter = speech_backend
        adapter_source = "[speech].backend"
    else:
        adapter = ""
        adapter_source = ""
        issues.append("local transcription adapter is not configured")
        guidance.append(
            "Set [voice_control].transcription_adapter to faster-whisper or "
            "whisper.cpp before enabling any external trigger."
        )
    if adapter and adapter not in LOCAL_TRANSCRIPTION_ADAPTERS:
        issues.append(f"unsupported local transcription adapter: {adapter}")
        guidance.append(
            f"Use a supported local adapter: {', '.join(LOCAL_TRANSCRIPTION_ADAPTERS)}."
        )

    model_path = _voice_doctor_model_path(config, adapter or "disabled")
    if model_path["required"] and not model_path["value"]:
        issues.append("required local transcription model path is missing")
        guidance.append(
            "Configure [voice_control].model_path or the required adapter model "
            "environment variable before running a real hotkey-triggered path."
        )
    elif model_path["required"] and model_path["exists"] is False:
        issues.append("configured local transcription model path does not exist")
        guidance.append(
            "Update the configured local transcription model path to an existing "
            "file before running a real hotkey-triggered path."
        )

    approval_required = bool(
        getattr(config.speech, "require_explicit_voice_approval", True)
    )
    if not approval_required:
        issues.append("[speech].require_explicit_voice_approval should remain true")
        guidance.append(
            "Keep [speech].require_explicit_voice_approval = true for external "
            "hotkey-triggered workflows."
        )

    resolved_base = str(getattr(voice_control, "default_api_base_url", "") or "")
    bridge = MacOSHotkeyBridgeCommand(
        jarvis_bin=str(
            getattr(voice_control, "hotkey_bridge_jarvis_bin", "jarvis") or "jarvis"
        ),
        duration=duration,
        recorder=recorder,
        input_device=str(
            getattr(voice_control, "hotkey_bridge_input_device", ":0") or ":0"
        ),
        adapter=adapter or None,
        base_url=resolved_base or None,
        session_id=str(getattr(voice_control, "hotkey_bridge_session_id", "") or "")
        or None,
    )
    argv = bridge.argv()

    return {
        "name": "OpenJarvis Hammerspoon push-to-talk runtime dry run",
        "version": 1,
        "ready": not issues,
        "resolved_preview_command": bridge.shell_command(),
        "resolved_argv": argv,
        "validation": {
            "issues": issues,
            "guidance": guidance,
            "duration_seconds": {
                "value": duration,
                "source": "[voice_control].default_record_duration"
                if raw_duration
                else "hotkey runtime fallback",
                "minimum": MICROPHONE_MIN_DURATION_SECONDS,
                "maximum": MICROPHONE_MAX_DURATION_SECONDS,
            },
            "recorder": {
                "value": recorder,
                "source": "[voice_control].hotkey_bridge_recorder",
                "allowed": list(MICROPHONE_RECORDER_KINDS),
            },
            "transcription_adapter": {
                "value": adapter,
                "source": adapter_source,
                "allowed": list(LOCAL_TRANSCRIPTION_ADAPTERS),
            },
            "model_path": model_path,
            "api_base_url": _configured_api_base_url(config),
            "approval_required": approval_required,
        },
        "safety": {
            "dry_run": True,
            "record_audio": False,
            "transcribe": False,
            "submit": False,
            "dispatch": False,
            "speak": False,
            "listener_started": False,
            "hammerspoon_init_modified": False,
            "hammerspoon_installed": False,
            "accessibility_permission_requested": False,
            "event_logged": False,
            "preview_only_default": True,
            "forbidden_default_flags_absent": all(
                flag not in argv for flag in ("--approve-dispatch", "--speak-result")
            ),
        },
    }


def _hotkey_runtime_preflight_data() -> dict[str, Any]:
    config = load_config()
    voice_control = _voice_control_config(config)
    issues: list[str] = []
    guidance: list[str] = []

    raw_duration = getattr(voice_control, "default_record_duration", 0.0) or 0.0
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        duration = 0.0
        issues.append("[voice_control].default_record_duration must be numeric")
        guidance.append(
            "Set [voice_control].default_record_duration to a bounded value "
            "between 0.1 and 30 seconds before wiring an external trigger."
        )

    duration_configured = (
        MICROPHONE_MIN_DURATION_SECONDS <= duration <= MICROPHONE_MAX_DURATION_SECONDS
    )
    if not duration_configured:
        issues.append(
            "[voice_control].default_record_duration must be configured between "
            f"{MICROPHONE_MIN_DURATION_SECONDS:g} and "
            f"{MICROPHONE_MAX_DURATION_SECONDS:g} seconds"
        )
        guidance.append(
            "Configure a fixed bounded duration so an external hotkey cannot "
            "start an unbounded recording."
        )

    recorder = str(getattr(voice_control, "hotkey_bridge_recorder", "macos") or "macos")
    recorder_status = recorder_diagnostics(recorder)
    real_recorder_configured = (
        recorder in MICROPHONE_RECORDER_KINDS
        and recorder_status["real_microphone_recorder_configured"] is True
        and recorder_status["supported"] is True
    )
    if not real_recorder_configured:
        issues.append(
            "[voice_control].hotkey_bridge_recorder must be macos or sounddevice"
        )
        guidance.append(
            "Set [voice_control].hotkey_bridge_recorder to a real microphone "
            "backend before wiring an external trigger."
        )

    configured_adapter = str(getattr(voice_control, "transcription_adapter", "") or "")
    speech_backend = str(getattr(config.speech, "backend", "") or "")
    if configured_adapter:
        adapter = configured_adapter
        adapter_source = "[voice_control].transcription_adapter"
    elif speech_backend in LOCAL_TRANSCRIPTION_ADAPTERS:
        adapter = speech_backend
        adapter_source = "[speech].backend"
    else:
        adapter = ""
        adapter_source = ""

    adapter_configured = adapter in LOCAL_TRANSCRIPTION_ADAPTERS
    if not adapter_configured:
        issues.append("local transcription adapter is not configured")
        guidance.append(
            "Set [voice_control].transcription_adapter to faster-whisper or "
            "whisper.cpp before wiring an external trigger."
        )

    model_path = _voice_doctor_model_path(config, adapter or "disabled")
    model_configured = bool(model_path["value"]) and model_path["exists"] is not False
    if not model_configured:
        issues.append("local transcription model is not configured")
        guidance.append(
            "Configure [voice_control].model_path, [speech].model, or the "
            "required adapter model environment variable before wiring an "
            "external trigger."
        )

    approval_required = bool(
        getattr(config.speech, "require_explicit_voice_approval", True)
    )
    if not approval_required:
        issues.append("[speech].require_explicit_voice_approval should remain true")
        guidance.append(
            "Keep [speech].require_explicit_voice_approval = true for external "
            "hotkey-triggered workflows."
        )

    api_base = _configured_api_base_url(config)
    api_base_configured = bool(api_base["value"])
    command_duration = duration if duration_configured else 2.0
    bridge = MacOSHotkeyBridgeCommand(
        jarvis_bin=str(
            getattr(voice_control, "hotkey_bridge_jarvis_bin", "jarvis") or "jarvis"
        ),
        duration=command_duration,
        recorder=recorder,
        input_device=str(
            getattr(voice_control, "hotkey_bridge_input_device", ":0") or ":0"
        ),
        adapter=adapter or None,
        base_url=api_base["value"] or None,
        session_id=str(getattr(voice_control, "hotkey_bridge_session_id", "") or "")
        or None,
    )
    argv = bridge.argv()
    forbidden_default_flags_absent = all(
        flag not in argv for flag in ("--approve-dispatch", "--speak-result")
    )
    hammerspoon_app = _hammerspoon_app_status()
    active_init = Path.home() / ".hammerspoon" / "init.lua"

    checks = {
        "resolved_preview_only_command": {
            "passed": forbidden_default_flags_absent,
            "value": bridge.shell_command(),
        },
        "real_recorder_backend_configured": {
            "passed": real_recorder_configured,
            "value": recorder,
            "source": "[voice_control].hotkey_bridge_recorder",
            "diagnostics": recorder_status,
        },
        "bounded_duration_configured": {
            "passed": duration_configured,
            "value": duration if duration > 0 else None,
            "source": "[voice_control].default_record_duration",
            "minimum": MICROPHONE_MIN_DURATION_SECONDS,
            "maximum": MICROPHONE_MAX_DURATION_SECONDS,
        },
        "local_transcription_adapter_model_configured": {
            "passed": adapter_configured and model_configured,
            "adapter": {
                "value": adapter,
                "source": adapter_source,
                "allowed": list(LOCAL_TRANSCRIPTION_ADAPTERS),
                "configured": adapter_configured,
            },
            "model": model_path,
        },
        "api_base_url_configured": {
            "passed": api_base_configured,
            "value": api_base["value"],
            "source": api_base["source"],
        },
        "approval_required": {
            "passed": approval_required,
            "config": "[speech].require_explicit_voice_approval",
        },
        "dispatch_disabled_by_default": {
            "passed": True,
            "approve_flag_present": "--approve-dispatch" in argv,
        },
        "speech_disabled_by_default": {
            "passed": True,
            "speak_flag_present": "--speak-result" in argv,
        },
        "hammerspoon_bridge_manual_activation_status": {
            "checked": True,
            "activation": "manual/deferred",
            "listener_started": False,
            "active_init_path": str(active_init),
            "active_init_exists": active_init.exists(),
            "bridge_reference_checked": False,
            "bridge_reference_check_reason": "no bridge path is used by preflight",
            "hammerspoon_app": hammerspoon_app,
        },
    }
    ready = all(check["passed"] for check in checks.values() if "passed" in check)

    return {
        "name": "OpenJarvis Hammerspoon push-to-talk runtime preflight",
        "version": 1,
        "ready": ready and not issues,
        "resolved_preview_command": bridge.shell_command(),
        "resolved_argv": argv,
        "checks": checks,
        "issues": issues,
        "guidance": guidance,
        "safety": {
            "preflight": True,
            "record_audio": False,
            "transcribe": False,
            "load_transcription_model": False,
            "submit": False,
            "dispatch": False,
            "speak": False,
            "listener_started": False,
            "hammerspoon_init_modified": False,
            "hammerspoon_installed": False,
            "accessibility_permission_requested": False,
            "approval_bypassed": False,
            "event_logged": False,
            "preview_only_default": True,
            "forbidden_default_flags_absent": forbidden_default_flags_absent,
        },
    }


def _hotkey_runtime_status_data() -> dict[str, Any]:
    config = load_config()
    voice_control = _voice_control_config(config)
    issues: list[str] = []
    guidance: list[str] = []

    raw_duration = getattr(voice_control, "default_record_duration", 0.0) or 0.0
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        duration = 0.0
        issues.append("[voice_control].default_record_duration must be numeric")
        guidance.append(
            "Set [voice_control].default_record_duration to a bounded value "
            "between 0.1 and 30 seconds before using the runtime trigger."
        )
    duration_ready = (
        MICROPHONE_MIN_DURATION_SECONDS <= duration <= MICROPHONE_MAX_DURATION_SECONDS
    )
    command_duration = duration if duration_ready else 2.0

    recorder = str(getattr(voice_control, "hotkey_bridge_recorder", "macos") or "macos")
    recorder_status = recorder_diagnostics(recorder)
    recorder_ready = (
        recorder in MICROPHONE_RECORDER_KINDS
        and recorder_status["real_microphone_recorder_configured"] is True
        and recorder_status["supported"] is True
    )
    if not recorder_ready:
        issues.append(
            "[voice_control].hotkey_bridge_recorder must be macos or sounddevice"
        )
        guidance.append(
            "Set [voice_control].hotkey_bridge_recorder to a real microphone "
            "backend before using the runtime trigger."
        )

    configured_adapter = str(getattr(voice_control, "transcription_adapter", "") or "")
    speech_backend = str(getattr(config.speech, "backend", "") or "")
    if configured_adapter:
        adapter = configured_adapter
        adapter_source = "[voice_control].transcription_adapter"
    elif speech_backend in LOCAL_TRANSCRIPTION_ADAPTERS:
        adapter = speech_backend
        adapter_source = "[speech].backend"
    else:
        adapter = ""
        adapter_source = ""

    adapter_ready = adapter in LOCAL_TRANSCRIPTION_ADAPTERS
    if not adapter_ready:
        issues.append("local transcription adapter is not configured")
        guidance.append(
            "Set [voice_control].transcription_adapter to faster-whisper or "
            "whisper.cpp before using the runtime trigger."
        )

    model_path = _voice_doctor_model_path(config, adapter or "disabled")
    model_ready = bool(model_path["value"]) and model_path["exists"] is not False
    if not model_ready:
        issues.append("local transcription model is not configured")
        guidance.append(
            "Configure [voice_control].model_path, [speech].model, or the "
            "required adapter model environment variable before using the "
            "runtime trigger."
        )

    approval_required = bool(
        getattr(config.speech, "require_explicit_voice_approval", True)
    )
    if not approval_required:
        issues.append("[speech].require_explicit_voice_approval should remain true")
        guidance.append(
            "Keep [speech].require_explicit_voice_approval = true for external "
            "hotkey-triggered workflows."
        )

    api_base = _configured_api_base_url(config)
    bridge = MacOSHotkeyBridgeCommand(
        jarvis_bin=str(
            getattr(voice_control, "hotkey_bridge_jarvis_bin", "jarvis") or "jarvis"
        ),
        duration=command_duration,
        recorder=recorder,
        input_device=str(
            getattr(voice_control, "hotkey_bridge_input_device", ":0") or ":0"
        ),
        adapter=adapter or None,
        base_url=api_base["value"] or None,
        session_id=str(getattr(voice_control, "hotkey_bridge_session_id", "") or "")
        or None,
    )
    trigger_argv = bridge.runtime_argv()
    preview_argv = bridge.argv()
    forbidden_default_flags_absent = all(
        flag not in trigger_argv + preview_argv
        for flag in ("--approve-dispatch", "--speak-result")
    )
    runtime_capabilities = {
        "contract_available": True,
        "dry_run_available": True,
        "preflight_available": True,
        "trigger_command_available": True,
    }
    safety = {
        "status": True,
        "preview_only_default": True,
        "dispatch_requires_explicit_approval": True,
        "speech_requires_dispatch_approval_and_speech_opt_in": True,
        "record_audio": False,
        "transcribe": False,
        "submit": False,
        "dispatch": False,
        "speak": False,
        "listener_started_by_python": False,
        "init_lua_mutated_by_jarvis": False,
        "accessibility_permission_requested_by_jarvis": False,
        "hammerspoon_installed_by_jarvis": False,
        "approval_bypassed": False,
        "lua_executed": False,
        "bridge_shell_commands_run": False,
        "event_logged": False,
        "forbidden_default_flags_absent": forbidden_default_flags_absent,
    }
    checks = {
        "runtime_contract_available": {
            "passed": runtime_capabilities["contract_available"],
            "command": "jarvis voice hotkey-runtime --contract",
        },
        "dry_run_available": {
            "passed": runtime_capabilities["dry_run_available"],
            "command": "jarvis voice hotkey-runtime --dry-run",
        },
        "preflight_available": {
            "passed": runtime_capabilities["preflight_available"],
            "command": "jarvis voice hotkey-runtime --preflight",
        },
        "trigger_command_available": {
            "passed": runtime_capabilities["trigger_command_available"],
            "command": "jarvis voice hotkey-runtime --trigger",
        },
        "preview_only_default": {
            "passed": safety["preview_only_default"] and forbidden_default_flags_absent,
        },
        "dispatch_requires_explicit_approval": {
            "passed": approval_required,
            "config": "[speech].require_explicit_voice_approval",
        },
        "speech_requires_dispatch_approval_plus_speech_opt_in": {
            "passed": True,
            "required_flags": ["--approve-dispatch", "--speak-result"],
        },
        "recorder_readiness": {
            "passed": recorder_ready,
            "value": recorder,
            "source": "[voice_control].hotkey_bridge_recorder",
            "diagnostics": recorder_status,
        },
        "duration_readiness": {
            "passed": duration_ready,
            "value": duration if duration > 0 else None,
            "source": "[voice_control].default_record_duration",
            "minimum": MICROPHONE_MIN_DURATION_SECONDS,
            "maximum": MICROPHONE_MAX_DURATION_SECONDS,
        },
        "transcription_model_readiness": {
            "passed": adapter_ready and model_ready,
            "adapter": {
                "value": adapter,
                "source": adapter_source,
                "allowed": list(LOCAL_TRANSCRIPTION_ADAPTERS),
                "configured": adapter_ready,
            },
            "model": model_path,
        },
        "api_base_url_readiness": {
            "passed": bool(api_base["value"]),
            "value": api_base["value"],
            "source": api_base["source"],
        },
        "event_logging_state": {
            "enabled": bool(getattr(voice_control, "voice_logs_enabled", True)),
            "path": str(getattr(voice_control, "voice_logs_path", "") or ""),
            "status_command_writes_event": False,
            "diagnostic_event_logged": False,
        },
        "listener_started_by_python": {"passed": True, "value": False},
        "init_lua_mutated_by_jarvis": {"passed": True, "value": False},
        "accessibility_permission_requested_by_jarvis": {
            "passed": True,
            "value": False,
        },
    }
    ready = (
        all(check["passed"] for check in checks.values() if "passed" in check)
        and not issues
    )

    return {
        "name": "OpenJarvis Hammerspoon push-to-talk runtime status",
        "version": 1,
        "ready": ready,
        "runtime_capabilities": runtime_capabilities,
        "generated_hammerspoon_bridge_expected_command": shlex.join(trigger_argv),
        "generated_hammerspoon_bridge_expected_argv": trigger_argv,
        "internal_preview_command": bridge.shell_command(),
        "internal_preview_argv": preview_argv,
        "checks": checks,
        "issues": issues,
        "guidance": guidance,
        "safety": safety,
    }


def _format_hotkey_runtime_contract(data: dict[str, Any]) -> None:
    state = data["state"]
    trigger = data["external_trigger"]
    command_path = data["default_command_path"]
    requirements = data["requirements"]

    click.echo("Voice hotkey runtime bridge contract")
    click.echo(f"  version: {data['version']}")
    click.echo("  status: disabled by default")
    click.echo("  Python listener started: False")
    click.echo("  ~/.hammerspoon/init.lua modified: False")
    click.echo(f"  Hammerspoon installed: {state['hammerspoon_installed']}")
    click.echo(
        "  Accessibility permission requested: "
        f"{state['accessibility_permission_requested']}"
    )
    click.echo("")
    click.echo("Accepted external trigger shape:")
    click.echo(f"  owner: {trigger['owner']}")
    click.echo(f"  required argv: {' '.join(trigger['shape'])}")
    click.echo(f"  optional flags: {', '.join(trigger['optional_flags'])}")
    click.echo(
        f"  forbidden by default: {', '.join(trigger['forbidden_default_flags'])}"
    )
    click.echo("")
    click.echo("Default command path:")
    click.echo(f"  command: {command_path['command']}")
    click.echo(f"  internal safe path: {command_path['internal_safe_path']}")
    click.echo(f"  behavior: {command_path['behavior']}")
    click.echo(f"  submit endpoint: {command_path['submit_endpoint']}")
    click.echo("  dispatch: skipped unless --approve-dispatch is present")
    click.echo("")
    click.echo("Runtime requirements:")
    duration = requirements["duration_seconds"]
    click.echo(
        f"  duration: required, {duration['minimum']:g}-{duration['maximum']:g} seconds"
    )
    recorder = requirements["recorder"]
    click.echo(f"  recorder: real backend required ({', '.join(recorder['allowed'])})")
    transcription = requirements["transcription"]
    click.echo(
        "  transcription: local adapter/model required "
        f"({', '.join(transcription['allowed_adapters'])})"
    )
    click.echo("  approval: dispatch only with explicit --approve-dispatch")
    click.echo("  speech: only with --speak-result after approved dispatch")
    click.echo("")
    click.echo("Expected exit codes:")
    for code, meaning in data["exit_codes"].items():
        click.echo(f"  {code}: {meaning}")
    click.echo("")
    click.echo("Expected stdout/stderr:")
    click.echo(f"  stdout: {data['stdio']['stdout']}")
    click.echo(f"  stderr: {data['stdio']['stderr']}")
    click.echo("")
    click.echo("Event logging:")
    event_logging = data["event_logging"]
    click.echo(f"  path: {event_logging['path']}")
    click.echo(f"  redaction: {event_logging['redaction']}")
    click.echo(f"  raw audio logged: {event_logging['raw_audio_logged']}")
    click.echo(
        "  contract command writes event: "
        f"{event_logging['contract_command_writes_event']}"
    )
    click.echo("")
    click.echo("Rollback and safety:")
    rollback = data["rollback_safety"]
    click.echo(f"  external rollback: {rollback['disable_external_capture']}")
    click.echo(f"  Jarvis rollback actions: {rollback['jarvis_rollback_actions']}")
    click.echo("  no approval bypass, automatic dispatch, or automatic speech")


def _format_hotkey_runtime_dry_run(data: dict[str, Any]) -> None:
    click.echo("Voice hotkey runtime dry run")
    click.echo(f"  ready: {data['ready']}")
    click.echo(f"  resolved preview command: {data['resolved_preview_command']}")
    click.echo("  behavior: preview-only")
    safety = data["safety"]
    click.echo(
        "  safety: "
        "no recording, transcription, submit, dispatch, speech, listeners, "
        "Hammerspoon install, init.lua edit, Accessibility request, or event log"
    )
    click.echo(
        f"  forbidden default flags absent: {safety['forbidden_default_flags_absent']}"
    )

    validation = data["validation"]
    click.echo("")
    click.echo("Resolved values:")
    duration = validation["duration_seconds"]
    click.echo(f"  duration: {duration['value']:g} seconds ({duration['source']})")
    recorder = validation["recorder"]
    click.echo(f"  recorder: {recorder['value']} ({recorder['source']})")
    adapter = validation["transcription_adapter"]
    click.echo(
        "  transcription_adapter: "
        f"{adapter['value'] or '-'} ({adapter['source'] or 'missing'})"
    )
    model = validation["model_path"]
    exists = model["exists"] if model["exists"] is not None else "not required"
    click.echo(
        f"  model_path: {model['value'] or '-'} "
        f"(required={model['required']}, exists={exists})"
    )
    api_base = validation["api_base_url"]
    click.echo(f"  api_base_url: {api_base['value']} ({api_base['source']})")
    click.echo(f"  approval_required: {validation['approval_required']}")

    if validation["issues"]:
        click.echo("")
        click.echo("Setup issues:")
        for issue in validation["issues"]:
            click.echo(f"  - {issue}")
    if validation["guidance"]:
        click.echo("")
        click.echo("Guidance:")
        for item in validation["guidance"]:
            click.echo(f"  - {item}")


def _format_hotkey_runtime_preflight(data: dict[str, Any]) -> None:
    click.echo("Voice hotkey runtime preflight")
    click.echo(f"  ready: {data['ready']}")
    click.echo(f"  resolved preview-only command: {data['resolved_preview_command']}")
    click.echo("  behavior: preview-only")
    safety = data["safety"]
    click.echo(
        "  safety: no recording, transcription, model loading, submit, dispatch, "
        "speech, listeners, Hammerspoon install, init.lua edit, Accessibility "
        "request, approval bypass, or event log"
    )
    click.echo(
        f"  forbidden default flags absent: {safety['forbidden_default_flags_absent']}"
    )

    checks = data["checks"]
    click.echo("")
    click.echo("Readiness checks:")
    resolved = checks["resolved_preview_only_command"]
    click.echo(f"  - resolved preview-only command: {resolved['passed']}")
    recorder = checks["real_recorder_backend_configured"]
    click.echo(
        "  - real recorder backend configured: "
        f"{recorder['passed']} ({recorder['value']})"
    )
    duration = checks["bounded_duration_configured"]
    duration_value = duration["value"] if duration["value"] is not None else "-"
    click.echo(
        "  - bounded duration configured: "
        f"{duration['passed']} ({duration_value} seconds)"
    )
    transcription = checks["local_transcription_adapter_model_configured"]
    click.echo(
        f"  - local transcription adapter/model configured: {transcription['passed']}"
    )
    click.echo(f"    adapter: {transcription['adapter']['value'] or '-'}")
    model = transcription["model"]
    exists = model["exists"] if model["exists"] is not None else "not required"
    click.echo(
        f"    model: {model['value'] or '-'} "
        f"(required={model['required']}, exists={exists})"
    )
    api_base = checks["api_base_url_configured"]
    click.echo(
        f"  - API base URL configured: {api_base['passed']} ({api_base['value']})"
    )
    click.echo(f"  - approval required: {checks['approval_required']['passed']}")
    dispatch = checks["dispatch_disabled_by_default"]
    approve_flag_present = dispatch["approve_flag_present"]
    click.echo(
        "  - dispatch disabled by default: "
        f"{dispatch['passed']} (approve flag present={approve_flag_present})"
    )
    speech = checks["speech_disabled_by_default"]
    click.echo(
        "  - speech disabled by default: "
        f"{speech['passed']} (speak flag present={speech['speak_flag_present']})"
    )
    activation = checks["hammerspoon_bridge_manual_activation_status"]
    click.echo("  - Hammerspoon bridge/manual activation status:")
    click.echo(f"    activation: {activation['activation']}")
    click.echo(f"    listener started: {activation['listener_started']}")
    click.echo(f"    active init path: {activation['active_init_path']}")
    click.echo(f"    active init exists: {activation['active_init_exists']}")
    click.echo(
        "    bridge reference checked: "
        f"{activation['bridge_reference_checked']} "
        f"({activation['bridge_reference_check_reason']})"
    )
    app_status = activation["hammerspoon_app"]
    if app_status["checked"]:
        click.echo(f"    Hammerspoon app detected: {app_status['detected']}")
    else:
        click.echo(
            f"    Hammerspoon app detected: not checked ({app_status['reason']})"
        )

    if data["issues"]:
        click.echo("")
        click.echo("Setup issues:")
        for issue in data["issues"]:
            click.echo(f"  - {issue}")
    if data["guidance"]:
        click.echo("")
        click.echo("Guidance:")
        for item in data["guidance"]:
            click.echo(f"  - {item}")


def _format_hotkey_runtime_status(data: dict[str, Any]) -> None:
    click.echo("Voice hotkey runtime status")
    click.echo(f"  ready: {data['ready']}")
    click.echo(
        "  generated Hammerspoon bridge expected command: "
        f"{data['generated_hammerspoon_bridge_expected_command']}"
    )
    click.echo(f"  internal preview path: {data['internal_preview_command']}")
    click.echo("  behavior: preview-only by default")

    checks = data["checks"]
    click.echo("")
    click.echo("Runtime trigger audit:")
    click.echo(
        "  - runtime contract available: "
        f"{checks['runtime_contract_available']['passed']}"
    )
    click.echo(f"  - dry-run available: {checks['dry_run_available']['passed']}")
    click.echo(f"  - preflight available: {checks['preflight_available']['passed']}")
    click.echo(
        "  - trigger command available: "
        f"{checks['trigger_command_available']['passed']}"
    )
    click.echo(f"  - preview-only default: {checks['preview_only_default']['passed']}")
    click.echo(
        "  - dispatch requires explicit approval: "
        f"{checks['dispatch_requires_explicit_approval']['passed']}"
    )
    click.echo(
        "  - speech requires explicit dispatch approval plus speech opt-in: "
        f"{checks['speech_requires_dispatch_approval_plus_speech_opt_in']['passed']}"
    )
    recorder = checks["recorder_readiness"]
    click.echo(f"  - recorder readiness: {recorder['passed']} ({recorder['value']})")
    duration = checks["duration_readiness"]
    duration_value = duration["value"] if duration["value"] is not None else "-"
    click.echo(
        f"  - duration readiness: {duration['passed']} ({duration_value} seconds)"
    )
    transcription = checks["transcription_model_readiness"]
    click.echo(f"  - transcription/model readiness: {transcription['passed']}")
    click.echo(f"    adapter: {transcription['adapter']['value'] or '-'}")
    model = transcription["model"]
    exists = model["exists"] if model["exists"] is not None else "not required"
    click.echo(
        f"    model: {model['value'] or '-'} "
        f"(required={model['required']}, exists={exists})"
    )
    api_base = checks["api_base_url_readiness"]
    click.echo(
        f"  - API base URL readiness: {api_base['passed']} ({api_base['value']})"
    )
    event_logging = checks["event_logging_state"]
    click.echo(
        "  - event logging state: "
        f"enabled={event_logging['enabled']}, "
        f"path={event_logging['path'] or '-'}, "
        "status command writes event=False"
    )
    click.echo(
        "  - listener started by Python: "
        f"{checks['listener_started_by_python']['value']}"
    )
    click.echo(
        "  - init.lua mutated by Jarvis: "
        f"{checks['init_lua_mutated_by_jarvis']['value']}"
    )
    click.echo(
        "  - Accessibility permission requested by Jarvis: "
        f"{checks['accessibility_permission_requested_by_jarvis']['value']}"
    )

    safety = data["safety"]
    click.echo("")
    click.echo(
        "Safety: no recording, transcription, submit, dispatch, speech, listeners, "
        "Lua execution, bridge shell commands, Hammerspoon install, init.lua "
        "mutation, Accessibility request, approval bypass, or event log"
    )
    click.echo(
        f"  forbidden default flags absent: {safety['forbidden_default_flags_absent']}"
    )

    if data["issues"]:
        click.echo("")
        click.echo("Setup issues:")
        for issue in data["issues"]:
            click.echo(f"  - {issue}")
    if data["guidance"]:
        click.echo("")
        click.echo("Guidance:")
        for item in data["guidance"]:
            click.echo(f"  - {item}")


@click.group("voice")
def voice() -> None:
    """Explicit local/manual voice flow over /v1/voice/ptt."""


@voice.command("hotkey-runtime")
@click.option(
    "--contract",
    is_flag=True,
    default=False,
    help="Print the disabled-by-default external Hammerspoon runtime contract.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help=(
        "Resolve the preview-only mic-run command an external Hammerspoon trigger "
        "would call, without running it."
    ),
)
@click.option(
    "--preflight",
    is_flag=True,
    default=False,
    help=(
        "Validate external Hammerspoon trigger readiness without recording, "
        "transcribing, dispatching, speaking, logging, or starting listeners."
    ),
)
@click.option(
    "--status",
    is_flag=True,
    default=False,
    help=(
        "Audit external Hammerspoon trigger readiness without running the "
        "trigger or starting listeners."
    ),
)
@click.option(
    "--trigger",
    is_flag=True,
    default=False,
    help=(
        "Run one bounded external trigger using the same safe path as mic-run. "
        "Preview-only unless --approve-dispatch is also passed."
    ),
)
@click.option(
    "--duration",
    type=click.FloatRange(
        min=MICROPHONE_MIN_DURATION_SECONDS,
        max=MICROPHONE_MAX_DURATION_SECONDS,
    ),
    default=None,
    help=(
        "Trigger recording duration in seconds. Required unless "
        "[voice_control].default_record_duration is configured."
    ),
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory for the temporary trigger WAV.",
)
@click.option(
    "--recorder",
    "recorder_kind",
    type=click.Choice(MICROPHONE_RECORDER_KINDS),
    default=None,
    help=(
        "Real microphone recorder for --trigger. Required unless configured in "
        "[voice_control].hotkey_bridge_recorder."
    ),
)
@click.option(
    "--input-device",
    default=None,
    help=(
        "Input device for --trigger. Defaults to "
        "[voice_control].hotkey_bridge_input_device."
    ),
)
@click.option(
    "--adapter",
    type=click.Choice(LOCAL_TRANSCRIPTION_ADAPTERS),
    default=None,
    help=(
        "Local transcription adapter for --trigger. Required unless configured "
        "in [voice_control].transcription_adapter."
    ),
)
@click.option("--language", default=None, help="Optional trigger language code hint.")
@click.option(
    "--session-id",
    default="",
    help=(
        "Optional trigger session id. Defaults to "
        "[voice_control].hotkey_bridge_session_id."
    ),
)
@click.option(
    "--agent-id",
    default="",
    help="Agent id to dispatch to after explicit --approve-dispatch.",
)
@click.option(
    "--approve-dispatch",
    is_flag=True,
    default=False,
    help="Explicitly approve and call /dispatch after the trigger preview.",
)
@click.option(
    "--speak-result",
    is_flag=True,
    default=False,
    help=(
        "Speak the dispatch result. Requires --approve-dispatch and never runs "
        "by default."
    ),
)
@click.option(
    "--speech-adapter",
    type=click.Choice(LOCAL_SPEECH_OUTPUT_ADAPTERS),
    default=None,
    help="Explicit local speech-output adapter for --speak-result.",
)
@click.option(
    "--voice",
    "voice_name",
    default=None,
    help="Optional macOS say voice name for --speak-result.",
)
@click.option(
    "--rate",
    type=click.IntRange(min=80, max=500),
    default=None,
    help="Optional macOS say speaking rate for --speak-result.",
)
@click.option(
    "--base-url",
    envvar="OPENJARVIS_BASE_URL",
    default=None,
    help="OpenJarvis API base URL for --trigger.",
)
@click.option(
    "--api-key",
    envvar="OPENJARVIS_API_KEY",
    default=None,
    help="API key for an authenticated local server.",
)
@click.option(
    "--timeout",
    default=10.0,
    show_default=True,
    help="HTTP timeout seconds for --trigger.",
)
@click.option(
    "--keep-file",
    is_flag=True,
    default=False,
    help="Keep the trigger WAV instead of deleting it after the run.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print the contract, dry-run, preflight, status, or trigger result as JSON.",
)
@click.pass_context
def hotkey_runtime(
    ctx: click.Context,
    contract: bool,
    dry_run: bool,
    preflight: bool,
    status: bool,
    trigger: bool,
    duration: float | None,
    output_dir: Path | None,
    recorder_kind: str | None,
    input_device: str | None,
    adapter: str | None,
    language: str | None,
    session_id: str,
    agent_id: str,
    approve_dispatch: bool,
    speak_result: bool,
    speech_adapter: str | None,
    voice_name: str | None,
    rate: int | None,
    base_url: str | None,
    api_key: str | None,
    timeout: float,
    keep_file: bool,
    as_json: bool,
) -> None:
    """Document, audit, or trigger the safe external hotkey runtime boundary."""
    selected_modes = sum((contract, dry_run, preflight, status, trigger))
    if selected_modes != 1:
        raise click.UsageError(
            "pass exactly one of --contract, --dry-run, --preflight, --status, "
            "or --trigger for hotkey runtime"
        )

    if contract:
        data = _hotkey_runtime_contract_data()
    elif dry_run:
        data = _hotkey_runtime_dry_run_data()
    elif status:
        data = _hotkey_runtime_status_data()
    elif trigger:
        if speak_result and not approve_dispatch:
            raise click.UsageError("--speak-result requires --approve-dispatch")
        resolved_duration = _record_duration(duration)
        _validate_bounded_microphone_duration(resolved_duration)
        resolved_recorder = _configured_hotkey_microphone_recorder_kind(recorder_kind)
        resolved_input_device = _configured_hotkey_input_device(input_device)
        resolved_session_id = _configured_hotkey_session_id(session_id)
        if not as_json:
            click.echo("Voice hotkey runtime trigger")
            click.echo("  mode: external single-shot")
            click.echo("  listener_started: False")
            click.echo("  hammerspoon_init_modified: False")
            click.echo("  accessibility_permission_requested: False")
            click.echo("  behavior: preview-only unless --approve-dispatch is present")
        ctx.invoke(
            mic_run,
            duration=resolved_duration,
            output_dir=output_dir,
            recorder_kind=resolved_recorder,
            input_device=resolved_input_device,
            adapter=adapter,
            language=language,
            session_id=resolved_session_id,
            agent_id=agent_id,
            approve_dispatch=approve_dispatch,
            speak_result=speak_result,
            speech_adapter=speech_adapter,
            voice_name=voice_name,
            rate=rate,
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            keep_file=keep_file,
            as_json=as_json,
        )
        return
    else:
        data = _hotkey_runtime_preflight_data()
    if as_json:
        _emit_json(data)
        return
    if contract:
        _format_hotkey_runtime_contract(data)
    elif dry_run:
        _format_hotkey_runtime_dry_run(data)
    elif status:
        _format_hotkey_runtime_status(data)
    else:
        _format_hotkey_runtime_preflight(data)


@voice.command("doctor")
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON diagnostics.")
def doctor(as_json: bool) -> None:
    """Inspect voice setup without recording, dispatching, speaking, or hotkeys."""
    data = _voice_doctor_data()
    _log_voice_event(
        "doctor",
        "diagnostics_result",
        details={
            "transcription_adapter": data["transcription_adapter"]["effective"],
            "speech_output": data["speech_output"]["effective"],
            "hotkeys_started": False,
            "dispatch_called": False,
            "speech_called": False,
        },
    )
    if as_json:
        _emit_json(data)
        return
    _format_voice_doctor(data)


@voice.command("hotkey-bridge")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["command", "hammerspoon", "json"]),
    default=None,
    help="Bridge output to print; never starts a listener.",
)
@click.option(
    "--duration",
    type=click.FloatRange(
        min=MICROPHONE_MIN_DURATION_SECONDS,
        max=MICROPHONE_MAX_DURATION_SECONDS,
    ),
    default=None,
    help=(
        "Duration to include in the printed mic-run command. Defaults to "
        "[voice_control].default_record_duration or 2.0."
    ),
)
@click.option(
    "--recorder",
    "recorder_kind",
    type=click.Choice(MICROPHONE_RECORDER_KINDS),
    default=None,
    help="Real microphone recorder to include in the printed mic-run command.",
)
@click.option(
    "--input-device",
    default=None,
    help="macOS avfoundation input device for --recorder macos.",
)
@click.option(
    "--adapter",
    type=click.Choice(LOCAL_TRANSCRIPTION_ADAPTERS),
    default=None,
    help=(
        "Local transcription adapter to include. If omitted, mic-run still "
        "requires a configured local adapter before manual execution."
    ),
)
@click.option("--language", default=None, help="Optional language code hint.")
@click.option(
    "--base-url",
    envvar="OPENJARVIS_BASE_URL",
    default=None,
    help="OpenJarvis API base URL to include in the printed command.",
)
@click.option(
    "--session-id",
    default="",
    help="Optional client-side session id to include in the printed command.",
)
@click.option(
    "--jarvis-bin",
    default=None,
    help="Executable name/path to include in the printed command.",
)
@click.option(
    "--write-hammerspoon",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Generated disabled bridge only: write a preview-only Hammerspoon Lua "
        "example to an explicit new path; never installs or enables it."
    ),
)
@click.option(
    "--validate-hammerspoon",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Validation only: statically read a generated Hammerspoon Lua example "
        "without running Lua or bridge commands."
    ),
)
@click.option(
    "--install-preview",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Install preview only: validate a generated Hammerspoon Lua example "
        "and print manual steps without changing files."
    ),
)
@click.option(
    "--activation-guide",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Manual activation guide only: validate a generated Hammerspoon Lua "
        "example, show preflight status, and print manual install/rollback "
        "steps without changing files."
    ),
)
@click.option(
    "--rollback-guide",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Manual rollback guide only: inspect a generated Hammerspoon Lua "
        "example when present and print backup/rollback steps without "
        "changing files."
    ),
)
@click.option(
    "--activation-status",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Manual activation readiness only: summarize bridge readiness and "
        "manual-only safety boundaries without executing or modifying anything."
    ),
)
@click.option(
    "--status",
    "status_path",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Status/readiness only: report read-only Hammerspoon bridge status "
        "without executing or modifying anything."
    ),
)
def hotkey_bridge(
    output_format: str | None,
    duration: float | None,
    recorder_kind: str | None,
    input_device: str | None,
    adapter: str | None,
    language: str | None,
    base_url: str | None,
    session_id: str,
    jarvis_bin: str | None,
    write_hammerspoon: Path | None,
    validate_hammerspoon: Path | None,
    install_preview: Path | None,
    activation_guide: Path | None,
    rollback_guide: Path | None,
    activation_status: Path | None,
    status_path: Path | None,
) -> None:
    """Print or explicitly write a disabled macOS hotkey bridge example."""
    if activation_status is not None:
        if write_hammerspoon is not None:
            raise click.UsageError(
                "--activation-status cannot be combined with --write-hammerspoon"
            )
        if validate_hammerspoon is not None:
            raise click.UsageError(
                "--activation-status cannot be combined with --validate-hammerspoon"
            )
        if install_preview is not None:
            raise click.UsageError(
                "--activation-status cannot be combined with --install-preview"
            )
        if activation_guide is not None:
            raise click.UsageError(
                "--activation-status cannot be combined with --activation-guide"
            )
        if rollback_guide is not None:
            raise click.UsageError(
                "--activation-status cannot be combined with --rollback-guide"
            )
        if status_path is not None:
            raise click.UsageError(
                "--activation-status cannot be combined with --status"
            )
        if output_format is not None:
            raise click.UsageError(
                "--activation-status cannot be combined with --format"
            )
        status_data = _hammerspoon_bridge_status(activation_status)
        status_data["manual_activation_checklist"] = (
            _manual_hotkey_activation_checklist(status_data, _voice_doctor_data())
        )
        _format_hammerspoon_activation_status(status_data)
        return

    if status_path is not None:
        if write_hammerspoon is not None:
            raise click.UsageError(
                "--status cannot be combined with --write-hammerspoon"
            )
        if validate_hammerspoon is not None:
            raise click.UsageError(
                "--status cannot be combined with --validate-hammerspoon"
            )
        if install_preview is not None:
            raise click.UsageError("--status cannot be combined with --install-preview")
        if activation_guide is not None:
            raise click.UsageError(
                "--status cannot be combined with --activation-guide"
            )
        if rollback_guide is not None:
            raise click.UsageError("--status cannot be combined with --rollback-guide")
        if output_format is not None:
            raise click.UsageError("--status cannot be combined with --format")
        _format_hammerspoon_bridge_status(_hammerspoon_bridge_status(status_path))
        return

    if install_preview is not None:
        if write_hammerspoon is not None:
            raise click.UsageError(
                "--install-preview cannot be combined with --write-hammerspoon"
            )
        if validate_hammerspoon is not None:
            raise click.UsageError(
                "--install-preview cannot be combined with --validate-hammerspoon"
            )
        if activation_guide is not None:
            raise click.UsageError(
                "--install-preview cannot be combined with --activation-guide"
            )
        if rollback_guide is not None:
            raise click.UsageError(
                "--install-preview cannot be combined with --rollback-guide"
            )
        if output_format is not None:
            raise click.UsageError("--install-preview cannot be combined with --format")
        validated_path = _validate_hammerspoon_bridge_file(install_preview)
        _format_hammerspoon_install_preview(validated_path)
        return

    if activation_guide is not None:
        if write_hammerspoon is not None:
            raise click.UsageError(
                "--activation-guide cannot be combined with --write-hammerspoon"
            )
        if validate_hammerspoon is not None:
            raise click.UsageError(
                "--activation-guide cannot be combined with --validate-hammerspoon"
            )
        if rollback_guide is not None:
            raise click.UsageError(
                "--activation-guide cannot be combined with --rollback-guide"
            )
        if output_format is not None:
            raise click.UsageError(
                "--activation-guide cannot be combined with --format"
            )
        validated_path = _validate_hammerspoon_bridge_file(activation_guide)
        _format_hammerspoon_activation_guide(validated_path)
        return

    if rollback_guide is not None:
        if write_hammerspoon is not None:
            raise click.UsageError(
                "--rollback-guide cannot be combined with --write-hammerspoon"
            )
        if validate_hammerspoon is not None:
            raise click.UsageError(
                "--rollback-guide cannot be combined with --validate-hammerspoon"
            )
        if output_format is not None:
            raise click.UsageError("--rollback-guide cannot be combined with --format")
        _format_hammerspoon_rollback_guide(rollback_guide)
        return

    if validate_hammerspoon is not None:
        if write_hammerspoon is not None:
            raise click.UsageError(
                "--validate-hammerspoon cannot be combined with --write-hammerspoon"
            )
        if activation_guide is not None:
            raise click.UsageError(
                "--validate-hammerspoon cannot be combined with --activation-guide"
            )
        if rollback_guide is not None:
            raise click.UsageError(
                "--validate-hammerspoon cannot be combined with --rollback-guide"
            )
        if output_format is not None:
            raise click.UsageError(
                "--validate-hammerspoon cannot be combined with --format"
            )
        validated_path = _validate_hammerspoon_bridge_file(validate_hammerspoon)
        click.echo(f"Hammerspoon bridge validation passed: {validated_path}")
        click.echo("  preview-only default: True")
        click.echo("  manual activation: user-performed outside Jarvis")
        return

    defaults = _hotkey_bridge_defaults()
    if duration is not None:
        bridge_duration = duration
    else:
        raw_duration = getattr(defaults, "default_record_duration", 0.0) or 0.0
        try:
            bridge_duration = float(raw_duration) or 2.0
        except (TypeError, ValueError) as exc:
            raise click.ClickException(
                "[voice_control].default_record_duration must be a positive number"
            ) from exc
    if not (
        MICROPHONE_MIN_DURATION_SECONDS
        <= bridge_duration
        <= MICROPHONE_MAX_DURATION_SECONDS
    ):
        raise click.ClickException(
            "hotkey bridge duration must be between "
            f"{MICROPHONE_MIN_DURATION_SECONDS:g} and "
            f"{MICROPHONE_MAX_DURATION_SECONDS:g} seconds"
        )
    if write_hammerspoon is not None and output_format not in {None, "hammerspoon"}:
        raise click.UsageError(
            "--write-hammerspoon cannot be combined with a non-Hammerspoon --format"
        )
    bridge_format = (
        "hammerspoon"
        if write_hammerspoon is not None
        else output_format or getattr(defaults, "hotkey_bridge_format", "command")
    )
    if bridge_format not in {"command", "hammerspoon", "json"}:
        raise click.ClickException(f"unsupported hotkey bridge format: {bridge_format}")
    bridge_recorder = recorder_kind or getattr(
        defaults,
        "hotkey_bridge_recorder",
        "macos",
    )
    if bridge_recorder not in MICROPHONE_RECORDER_KINDS:
        raise click.ClickException(
            "hotkey bridge requires a real microphone recorder: macos or sounddevice"
        )
    resolved_adapter = adapter or getattr(defaults, "transcription_adapter", "") or None
    if resolved_adapter and resolved_adapter not in LOCAL_TRANSCRIPTION_ADAPTERS:
        raise click.ClickException(
            f"unsupported local transcription adapter: {resolved_adapter}"
        )
    resolved_base = base_url or getattr(defaults, "default_api_base_url", "") or None
    resolved_session = (
        session_id or getattr(defaults, "hotkey_bridge_session_id", "") or None
    )
    bridge = MacOSHotkeyBridgeCommand(
        jarvis_bin=jarvis_bin
        or getattr(defaults, "hotkey_bridge_jarvis_bin", "jarvis"),
        duration=bridge_duration,
        recorder=bridge_recorder,
        input_device=input_device
        or getattr(defaults, "hotkey_bridge_input_device", ":0"),
        adapter=resolved_adapter,
        language=language,
        base_url=resolved_base,
        session_id=resolved_session,
    )
    command = bridge.shell_command()
    _log_voice_event(
        "hotkey-bridge",
        "bridge_preview",
        details={
            "format": bridge_format,
            "recorder": bridge_recorder,
            "adapter": resolved_adapter or "",
            "listener_started": False,
            "global_key_capture": False,
            "dispatch_enabled": False,
            "speech_enabled": False,
        },
    )

    if bridge_format == "json":
        _emit_json(
            {
                "enabled": False,
                "listener_started": False,
                "global_key_capture": False,
                "dispatch_enabled": False,
                "speech_enabled": False,
                "command": command,
                "argv": bridge.argv(),
            }
        )
        return

    if bridge_format == "hammerspoon":
        snippet = bridge.hammerspoon_snippet()
        if write_hammerspoon is not None:
            written_path = _write_hammerspoon_bridge(write_hammerspoon, snippet)
            click.echo(f"Wrote disabled Hammerspoon bridge example: {written_path}")
            click.echo("  preview-only default: True")
            click.echo("  manual activation: user-performed outside Jarvis")
            return
        click.echo(snippet.rstrip())
        return

    click.echo("macOS hotkey bridge (disabled)")
    click.echo(f"  command: {command}")
    click.echo("  listener: disabled; no global key capture is started")
    click.echo("  dispatch: skipped; command omits --approve-dispatch")
    click.echo("  speech: skipped; command omits --speak-result")


@voice.command("submit")
@click.argument("transcript", nargs=-1, required=True)
@click.option("--agent-id", default="", help="Agent id to dispatch to after approval.")
@click.option("--session-id", default="", help="Optional client-side session id.")
@click.option(
    "--approve-dispatch",
    is_flag=True,
    default=False,
    help="Explicitly approve and call /dispatch after preview.",
)
@click.option(
    "--base-url",
    envvar="OPENJARVIS_BASE_URL",
    default=None,
    help="OpenJarvis API base URL. Defaults to configured local server.",
)
@click.option(
    "--api-key",
    envvar="OPENJARVIS_API_KEY",
    default=None,
    help="API key for an authenticated local server.",
)
@click.option(
    "--timeout",
    default=10.0,
    show_default=True,
    help="HTTP timeout seconds.",
)
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON responses.")
def submit(
    transcript: tuple[str, ...],
    agent_id: str,
    session_id: str,
    approve_dispatch: bool,
    base_url: str | None,
    api_key: str | None,
    timeout: float,
    as_json: bool,
) -> None:
    """Submit a typed transcript for preview; dispatch only with approval."""
    text = " ".join(transcript).strip()
    if not text:
        raise click.UsageError("transcript must not be empty")

    resolved_base = _base_url(base_url)
    resolved_key = _api_key(api_key)
    preview = _post_json(
        "/v1/voice/ptt/submit-transcript",
        {"transcript": text, "session_id": session_id},
        base_url=resolved_base,
        api_key=resolved_key,
        timeout=timeout,
    )
    _log_voice_event(
        "submit",
        "preview_result",
        transcript=text,
        details=_preview_log_details(preview),
    )

    if as_json:
        output: dict[str, Any] = {"preview": preview}
    else:
        _format_preview(preview)

    if not approve_dispatch:
        _log_voice_event(
            "submit",
            "dispatch_decision",
            status="skipped",
            transcript=text,
            details={
                "approved": False,
                "attempted": False,
                "reason": "missing --approve-dispatch",
            },
        )
        if as_json:
            output["dispatch_skipped"] = True
            output["dispatch_reason"] = "missing --approve-dispatch"
            _emit_json(output)
        else:
            click.echo("  dispatch: skipped (pass --approve-dispatch to run)")
        return

    dispatch = _post_json(
        "/v1/voice/ptt/dispatch",
        {"transcript": text, "agent_id": agent_id, "approved": True},
        base_url=resolved_base,
        api_key=resolved_key,
        timeout=timeout,
    )
    _log_voice_event(
        "submit",
        "dispatch_result",
        transcript=text,
        details=_dispatch_log_details(dispatch, approved=True, agent_id=agent_id),
    )
    if as_json:
        output["dispatch"] = dispatch
        _emit_json(output)
    else:
        _format_dispatch(dispatch)


@voice.command("transcribe-file")
@click.argument(
    "audio_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--adapter",
    type=click.Choice(LOCAL_TRANSCRIPTION_ADAPTERS),
    default=None,
    help=(
        "Local transcription adapter to use. If omitted, [speech].backend must "
        "be explicitly set to a local adapter."
    ),
)
@click.option("--language", default=None, help="Optional language code hint.")
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON response.")
def transcribe_file(
    audio_file: Path,
    adapter: str | None,
    language: str | None,
    as_json: bool,
) -> None:
    """Transcribe a local audio file; never dispatch automatically."""
    data = _transcribe_audio_file(audio_file, adapter=adapter, language=language)
    data["dispatch_skipped"] = True
    data["dispatch_reason"] = "file transcription does not dispatch"
    _log_voice_event(
        "transcribe-file",
        "transcription_result",
        transcript=str(data.get("text") or ""),
        details={
            "audio_file": str(audio_file),
            "adapter": data.get("backend") or adapter or "",
            "language": data.get("language") or "",
            "duration_seconds": data.get("duration_seconds"),
            "dispatch_skipped": True,
            "dispatch_reason": "file transcription does not dispatch",
        },
    )
    if as_json:
        _emit_json(data)
        return

    click.echo("Voice file transcription")
    click.echo(f"  adapter: {data.get('backend') or adapter}")
    if data.get("language"):
        click.echo(f"  language: {data['language']}")
    click.echo(f"  transcript: {data.get('text', '')}")
    click.echo("  dispatch: skipped (review, then use `jarvis voice submit ...`)")


@voice.command("speak")
@click.argument("text", nargs=-1, required=True)
@click.option(
    "--adapter",
    type=click.Choice(LOCAL_SPEECH_OUTPUT_ADAPTERS),
    default=None,
    help="Explicit local speech-output adapter.",
)
@click.option(
    "--voice",
    "voice_name",
    default=None,
    help="Optional macOS say voice name.",
)
@click.option(
    "--rate",
    type=click.IntRange(min=80, max=500),
    default=None,
    help="Optional macOS say speaking rate.",
)
def speak(
    text: tuple[str, ...],
    adapter: str | None,
    voice_name: str | None,
    rate: int | None,
) -> None:
    """Speak text locally only when explicitly requested."""
    speech_text = " ".join(text).strip()
    if not speech_text:
        raise click.UsageError("text must not be empty")

    resolved_adapter = _speech_output_adapter(adapter)
    resolved_voice = _speech_voice(voice_name)
    resolved_rate = _speech_rate(rate)
    output = _build_speech_output(
        resolved_adapter,
        voice_name=resolved_voice,
        rate=resolved_rate,
    )
    try:
        output.speak(speech_text)
    except (OSError, SpeechOutputUnavailableError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    _log_voice_event(
        "speak",
        "speech_result",
        transcript=speech_text,
        details={
            "adapter": resolved_adapter,
            "spoken": True,
            "dispatch_skipped": True,
        },
    )

    click.echo("Voice speech output")
    click.echo(f"  adapter: {resolved_adapter}")
    click.echo("  dispatch: skipped")


@voice.command("record-local")
@click.option(
    "--duration",
    type=click.FloatRange(min=0.1),
    default=None,
    help=(
        "Recording duration in seconds; required unless "
        "[voice_control].default_record_duration is set. Real microphone "
        "recording is limited to 0.1 to 30 seconds."
    ),
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory for the recorded WAV. Defaults to the system temp directory.",
)
@click.option(
    "--recorder",
    "recorder_kind",
    type=click.Choice(RECORDER_KINDS),
    default=None,
    help=(
        "Local recorder implementation. Defaults to "
        "[voice_control].default_recorder or dev-silent."
    ),
)
@click.option(
    "--input-device",
    default=":0",
    show_default=True,
    help="macOS avfoundation input device for --recorder macos.",
)
def record_local(
    duration: float | None,
    output_dir: Path | None,
    recorder_kind: str | None,
    input_device: str,
) -> None:
    """Record only to a local WAV; do not transcribe, preview, or dispatch."""
    resolved_duration = _record_duration(duration)
    resolved_recorder = _configured_recorder_kind(recorder_kind)
    _validate_real_microphone_duration(resolved_recorder, resolved_duration)
    handle = _record_local_audio(
        duration=resolved_duration,
        output_dir=output_dir,
        recorder_kind=resolved_recorder,
        input_device=input_device,
    )
    _log_voice_event(
        "record-local",
        "recording_result",
        details={
            "path": str(handle.path),
            "recorder": resolved_recorder,
            "duration": resolved_duration,
            "transcribed": False,
            "dispatch_skipped": True,
        },
    )
    click.echo(str(handle.path))


@voice.command("mic-smoke")
@click.option(
    "--duration",
    type=click.FloatRange(
        min=MICROPHONE_MIN_DURATION_SECONDS,
        max=MICROPHONE_MAX_DURATION_SECONDS,
    ),
    required=True,
    help="Explicit recording duration in seconds (0.1 to 30).",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory for the temporary WAV. Defaults to the system temp directory.",
)
@click.option(
    "--recorder",
    "recorder_kind",
    type=click.Choice(MICROPHONE_RECORDER_KINDS),
    default=None,
    help=(
        "Real microphone recorder. Required unless macos or sounddevice is set "
        "in [voice_control].default_recorder."
    ),
)
@click.option(
    "--input-device",
    default=":0",
    show_default=True,
    help="Input device for the selected recorder backend.",
)
@click.option(
    "--keep-file",
    is_flag=True,
    default=False,
    help="Keep the recorded WAV instead of deleting it after inspection.",
)
def mic_smoke(
    duration: float,
    output_dir: Path | None,
    recorder_kind: str | None,
    input_device: str,
    keep_file: bool,
) -> None:
    """Record only from a real mic and inspect the bounded local WAV."""
    resolved_recorder = _configured_microphone_recorder_kind(recorder_kind)
    handle = _record_local_audio(
        duration=duration,
        output_dir=output_dir,
        recorder_kind=resolved_recorder,
        input_device=input_device,
        cleanup_on_error=True,
    )
    try:
        metadata = inspect_wav_file(handle.path)
    except VoiceRecordingError as exc:
        if not keep_file:
            try:
                handle.path.unlink(missing_ok=True)
            except OSError as cleanup_exc:
                raise click.ClickException(
                    f"{exc} The invalid recording also could not be deleted: "
                    f"{cleanup_exc}"
                ) from cleanup_exc
        raise click.ClickException(str(exc)) from exc

    if not keep_file:
        try:
            handle.path.unlink()
        except OSError as exc:
            raise click.ClickException(
                f"recording passed inspection but could not be deleted: {exc}"
            ) from exc

    _log_voice_event(
        "mic-smoke",
        "microphone_smoke_result",
        details={
            "path": str(handle.path),
            "recorder": resolved_recorder,
            "requested_duration_seconds": duration,
            "file_kept": keep_file,
            "transcribed": False,
            "submitted": False,
            "dispatched": False,
            "spoken": False,
            **metadata,
        },
    )
    click.echo("Microphone smoke test")
    click.echo(f"  recorder: {resolved_recorder}")
    click.echo(f"  requested_duration_seconds: {duration}")
    click.echo(f"  path: {handle.path}")
    for key, value in metadata.items():
        click.echo(f"  {key}: {value}")
    click.echo(f"  file_kept: {keep_file}")
    click.echo("  transcription: skipped")
    click.echo("  submission: skipped")
    click.echo("  dispatch: skipped")
    click.echo("  speech: skipped")


@voice.command("mic-transcribe-smoke")
@click.option(
    "--duration",
    type=click.FloatRange(
        min=MICROPHONE_MIN_DURATION_SECONDS,
        max=MICROPHONE_MAX_DURATION_SECONDS,
    ),
    required=True,
    help="Explicit recording duration in seconds (0.1 to 30).",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory for the temporary WAV. Defaults to the system temp directory.",
)
@click.option(
    "--recorder",
    "recorder_kind",
    type=click.Choice(MICROPHONE_RECORDER_KINDS),
    default=None,
    help=(
        "Real microphone recorder. Required unless macos or sounddevice is set "
        "in [voice_control].default_recorder."
    ),
)
@click.option(
    "--input-device",
    default=":0",
    show_default=True,
    help="Input device for the selected recorder backend.",
)
@click.option(
    "--adapter",
    type=click.Choice(LOCAL_TRANSCRIPTION_ADAPTERS),
    default=None,
    help=(
        "Local transcription adapter. Required unless configured in "
        "[voice_control].transcription_adapter."
    ),
)
@click.option("--language", default=None, help="Optional language code hint.")
@click.option(
    "--keep-file",
    is_flag=True,
    default=False,
    help="Keep the recorded WAV instead of deleting it after transcription.",
)
def mic_transcribe_smoke(
    duration: float,
    output_dir: Path | None,
    recorder_kind: str | None,
    input_device: str,
    adapter: str | None,
    language: str | None,
    keep_file: bool,
) -> None:
    """Record from a real mic and transcribe locally; do not preview/dispatch."""
    resolved_recorder = _configured_microphone_recorder_kind(recorder_kind)
    adapter_id, transcriber = _build_transcriber(adapter)
    handle = _record_local_audio(
        duration=duration,
        output_dir=output_dir,
        recorder_kind=resolved_recorder,
        input_device=input_device,
        cleanup_on_error=True,
    )

    try:
        wav_metadata = inspect_wav_file(handle.path)
        transcription = transcriber.transcribe_file(handle.path, language=language)
    except (OSError, TranscriptionUnavailableError, VoiceRecordingError) as exc:
        if not keep_file:
            try:
                handle.path.unlink(missing_ok=True)
            except OSError as cleanup_exc:
                raise click.ClickException(
                    f"{exc} The temporary WAV also could not be deleted: {cleanup_exc}"
                ) from cleanup_exc
        raise click.ClickException(str(exc)) from exc

    transcription_data = transcription.to_dict()
    if not keep_file:
        try:
            handle.path.unlink()
        except OSError as exc:
            raise click.ClickException(
                f"transcription succeeded but the temporary WAV could not be "
                f"deleted: {exc}"
            ) from exc

    transcript = str(transcription_data.get("text") or "")
    _log_voice_event(
        "mic-transcribe-smoke",
        "microphone_transcription_smoke_result",
        transcript=transcript,
        details={
            "path": str(handle.path),
            "recorder": resolved_recorder,
            "requested_duration_seconds": duration,
            "file_kept": keep_file,
            "adapter": transcription_data.get("backend") or adapter_id,
            "language": transcription_data.get("language") or "",
            "transcription_duration_seconds": transcription_data.get(
                "duration_seconds"
            ),
            "submitted": False,
            "dispatched": False,
            "spoken": False,
            **wav_metadata,
        },
    )

    click.echo("Microphone transcription smoke test")
    click.echo(f"  recorder: {resolved_recorder}")
    click.echo(f"  requested_duration_seconds: {duration}")
    click.echo(f"  path: {handle.path}")
    for key, value in wav_metadata.items():
        click.echo(f"  {key}: {value}")
    click.echo(f"  file_kept: {keep_file}")
    click.echo(f"  adapter: {transcription_data.get('backend') or adapter_id}")
    if transcription_data.get("language"):
        click.echo(f"  language: {transcription_data['language']}")
    if transcription_data.get("confidence") is not None:
        click.echo(f"  confidence: {transcription_data['confidence']}")
    click.echo(
        "  transcription_duration_seconds: "
        f"{transcription_data.get('duration_seconds', 0.0)}"
    )
    click.echo(f"  transcript: {transcript}")
    click.echo("  submission: skipped")
    click.echo("  dispatch: skipped")
    click.echo("  speech: skipped")


@voice.command("mic-preview")
@click.option(
    "--duration",
    type=click.FloatRange(
        min=MICROPHONE_MIN_DURATION_SECONDS,
        max=MICROPHONE_MAX_DURATION_SECONDS,
    ),
    required=True,
    help="Explicit recording duration in seconds (0.1 to 30).",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory for the temporary WAV. Defaults to the system temp directory.",
)
@click.option(
    "--recorder",
    "recorder_kind",
    type=click.Choice(MICROPHONE_RECORDER_KINDS),
    default=None,
    help=(
        "Real microphone recorder. Required unless macos or sounddevice is set "
        "in [voice_control].default_recorder."
    ),
)
@click.option(
    "--input-device",
    default=":0",
    show_default=True,
    help="Input device for the selected recorder backend.",
)
@click.option(
    "--adapter",
    type=click.Choice(LOCAL_TRANSCRIPTION_ADAPTERS),
    default=None,
    help=(
        "Local transcription adapter. Required unless configured in "
        "[voice_control].transcription_adapter."
    ),
)
@click.option("--language", default=None, help="Optional language code hint.")
@click.option(
    "--session-id",
    default="",
    help="Optional client-side session id for the preview request.",
)
@click.option(
    "--base-url",
    envvar="OPENJARVIS_BASE_URL",
    default=None,
    help="OpenJarvis API base URL. Defaults to configured local server.",
)
@click.option(
    "--api-key",
    envvar="OPENJARVIS_API_KEY",
    default=None,
    help="API key for an authenticated local server.",
)
@click.option(
    "--timeout",
    default=10.0,
    show_default=True,
    help="HTTP timeout seconds.",
)
@click.option(
    "--keep-file",
    is_flag=True,
    default=False,
    help="Keep the recorded WAV instead of deleting it after preview.",
)
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON response.")
def mic_preview(
    duration: float,
    output_dir: Path | None,
    recorder_kind: str | None,
    input_device: str,
    adapter: str | None,
    language: str | None,
    session_id: str,
    base_url: str | None,
    api_key: str | None,
    timeout: float,
    keep_file: bool,
    as_json: bool,
) -> None:
    """Record and transcribe from a real mic, then submit a preview only."""
    resolved_recorder = _configured_microphone_recorder_kind(recorder_kind)
    adapter_id, transcriber = _build_transcriber(adapter)
    handle = _record_local_audio(
        duration=duration,
        output_dir=output_dir,
        recorder_kind=resolved_recorder,
        input_device=input_device,
        cleanup_on_error=True,
    )

    try:
        wav_metadata = inspect_wav_file(handle.path)
        transcription_result = transcriber.transcribe_file(
            handle.path,
            language=language,
        )
        transcription = transcription_result.to_dict()
        transcript = str(transcription.get("text") or "")
        preview = _post_json(
            "/v1/voice/ptt/submit-transcript",
            {"transcript": transcript, "session_id": session_id},
            base_url=_base_url(base_url),
            api_key=_api_key(api_key),
            timeout=timeout,
        )
    except (
        OSError,
        TranscriptionUnavailableError,
        VoiceRecordingError,
        click.ClickException,
    ) as exc:
        if not keep_file:
            try:
                handle.path.unlink(missing_ok=True)
            except OSError as cleanup_exc:
                raise click.ClickException(
                    f"{exc} The temporary WAV also could not be deleted: {cleanup_exc}"
                ) from cleanup_exc
        if isinstance(exc, click.ClickException):
            raise
        raise click.ClickException(str(exc)) from exc

    if not keep_file:
        try:
            handle.path.unlink()
        except OSError as exc:
            raise click.ClickException(
                f"preview succeeded but the temporary WAV could not be deleted: {exc}"
            ) from exc

    preview_details = _preview_log_details(preview)
    preview_details.update(
        {
            "recording_path": str(handle.path),
            "recorder": resolved_recorder,
            "requested_duration_seconds": duration,
            "file_kept": keep_file,
            "adapter": transcription.get("backend") or adapter_id,
            "language": transcription.get("language") or "",
            "dispatched": False,
            "spoken": False,
            **wav_metadata,
        }
    )
    _log_voice_event(
        "mic-preview",
        "preview_result",
        transcript=transcript,
        details=preview_details,
    )

    if as_json:
        _emit_json(
            {
                "recording": {
                    "path": str(handle.path),
                    "recorder": resolved_recorder,
                    "requested_duration_seconds": duration,
                    "file_kept": keep_file,
                    **wav_metadata,
                },
                "transcription": transcription,
                "preview": preview,
                "dispatch_skipped": True,
                "dispatch_reason": "mic-preview does not dispatch",
                "speech_skipped": True,
                "speech_reason": "mic-preview does not speak",
            }
        )
        return

    click.echo("Microphone preview")
    click.echo(f"  recorder: {resolved_recorder}")
    click.echo(f"  requested_duration_seconds: {duration}")
    click.echo(f"  path: {handle.path}")
    click.echo(f"  file_kept: {keep_file}")
    click.echo(f"  adapter: {transcription.get('backend') or adapter_id}")
    if transcription.get("language"):
        click.echo(f"  language: {transcription['language']}")
    click.echo(f"  transcript: {transcript}")
    _format_preview(preview)
    click.echo("  dispatch: skipped (mic-preview is preview-only)")
    click.echo("  speech: skipped (mic-preview never speaks)")


@voice.command("mic-run")
@click.option(
    "--duration",
    type=click.FloatRange(
        min=MICROPHONE_MIN_DURATION_SECONDS,
        max=MICROPHONE_MAX_DURATION_SECONDS,
    ),
    required=True,
    help="Explicit recording duration in seconds (0.1 to 30).",
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory for the temporary WAV. Defaults to the system temp directory.",
)
@click.option(
    "--recorder",
    "recorder_kind",
    type=click.Choice(MICROPHONE_RECORDER_KINDS),
    default=None,
    help=(
        "Real microphone recorder. Required unless macos or sounddevice is set "
        "in [voice_control].default_recorder."
    ),
)
@click.option(
    "--input-device",
    default=":0",
    show_default=True,
    help="Input device for the selected recorder backend.",
)
@click.option(
    "--adapter",
    type=click.Choice(LOCAL_TRANSCRIPTION_ADAPTERS),
    default=None,
    help=(
        "Local transcription adapter. Required unless configured in "
        "[voice_control].transcription_adapter."
    ),
)
@click.option("--language", default=None, help="Optional language code hint.")
@click.option(
    "--session-id",
    default="",
    help="Optional client-side session id for the preview request.",
)
@click.option("--agent-id", default="", help="Agent id to dispatch to after approval.")
@click.option(
    "--approve-dispatch",
    is_flag=True,
    default=False,
    help="Explicitly approve and call /dispatch after preview.",
)
@click.option(
    "--speak-result",
    is_flag=True,
    default=False,
    help="Speak the dispatch result through an explicit local speech-output adapter.",
)
@click.option(
    "--speech-adapter",
    type=click.Choice(LOCAL_SPEECH_OUTPUT_ADAPTERS),
    default=None,
    help="Explicit local speech-output adapter for --speak-result.",
)
@click.option(
    "--voice",
    "voice_name",
    default=None,
    help="Optional macOS say voice name for --speak-result.",
)
@click.option(
    "--rate",
    type=click.IntRange(min=80, max=500),
    default=None,
    help="Optional macOS say speaking rate for --speak-result.",
)
@click.option(
    "--base-url",
    envvar="OPENJARVIS_BASE_URL",
    default=None,
    help="OpenJarvis API base URL. Defaults to configured local server.",
)
@click.option(
    "--api-key",
    envvar="OPENJARVIS_API_KEY",
    default=None,
    help="API key for an authenticated local server.",
)
@click.option(
    "--timeout",
    default=10.0,
    show_default=True,
    help="HTTP timeout seconds.",
)
@click.option(
    "--keep-file",
    is_flag=True,
    default=False,
    help="Keep the recorded WAV instead of deleting it after the run.",
)
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON response.")
def mic_run(
    duration: float,
    output_dir: Path | None,
    recorder_kind: str | None,
    input_device: str,
    adapter: str | None,
    language: str | None,
    session_id: str,
    agent_id: str,
    approve_dispatch: bool,
    speak_result: bool,
    speech_adapter: str | None,
    voice_name: str | None,
    rate: int | None,
    base_url: str | None,
    api_key: str | None,
    timeout: float,
    keep_file: bool,
    as_json: bool,
) -> None:
    """Record, transcribe, and preview a real mic; approved dispatch is opt-in."""
    if speak_result and not approve_dispatch:
        raise click.UsageError("--speak-result requires --approve-dispatch")

    resolved_recorder = _configured_microphone_recorder_kind(recorder_kind)
    adapter_id, transcriber = _build_transcriber(adapter)
    resolved_base = _base_url(base_url)
    resolved_key = _api_key(api_key)
    handle = _record_local_audio(
        duration=duration,
        output_dir=output_dir,
        recorder_kind=resolved_recorder,
        input_device=input_device,
        cleanup_on_error=True,
    )

    pipeline_error: Exception | None = None
    dispatch: dict[str, Any] | None = None
    speech: dict[str, Any] | None = None
    try:
        wav_metadata = inspect_wav_file(handle.path)
        transcription_result = transcriber.transcribe_file(
            handle.path,
            language=language,
        )
        transcription = transcription_result.to_dict()
        transcript = str(transcription.get("text") or "")
        preview = _post_json(
            "/v1/voice/ptt/submit-transcript",
            {"transcript": transcript, "session_id": session_id},
            base_url=resolved_base,
            api_key=resolved_key,
            timeout=timeout,
        )
        if approve_dispatch:
            dispatch = _post_json(
                "/v1/voice/ptt/dispatch",
                {"transcript": transcript, "agent_id": agent_id, "approved": True},
                base_url=resolved_base,
                api_key=resolved_key,
                timeout=timeout,
            )
            if speak_result:
                speech_text = _dispatch_speech_text(dispatch)
                resolved_speech_adapter = _speech_output_adapter(speech_adapter)
                output = _build_speech_output(
                    resolved_speech_adapter,
                    voice_name=_speech_voice(voice_name),
                    rate=_speech_rate(rate),
                )
                output.speak(speech_text)
                speech = {"adapter": resolved_speech_adapter, "spoken": True}
    except (
        OSError,
        TranscriptionUnavailableError,
        VoiceRecordingError,
        SpeechOutputUnavailableError,
        ValueError,
        click.ClickException,
    ) as exc:
        pipeline_error = exc

    if not keep_file:
        try:
            handle.path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            message = "The temporary WAV could not be deleted"
            if pipeline_error is not None:
                message = f"{pipeline_error} {message}"
            raise click.ClickException(f"{message}: {cleanup_exc}") from cleanup_exc

    if pipeline_error is not None:
        if isinstance(pipeline_error, click.ClickException):
            raise pipeline_error
        raise click.ClickException(str(pipeline_error)) from pipeline_error

    preview_details = _preview_log_details(preview)
    preview_details.update(
        {
            "recording_path": str(handle.path),
            "recorder": resolved_recorder,
            "requested_duration_seconds": duration,
            "file_kept": keep_file,
            "adapter": transcription.get("backend") or adapter_id,
            "language": transcription.get("language") or "",
            "dispatched": dispatch is not None,
            "spoken": speech is not None,
            **wav_metadata,
        }
    )
    _log_voice_event(
        "mic-run",
        "preview_result",
        transcript=transcript,
        details=preview_details,
    )
    if dispatch is None:
        _log_voice_event(
            "mic-run",
            "dispatch_decision",
            status="skipped",
            transcript=transcript,
            details={
                "approved": False,
                "attempted": False,
                "reason": "missing --approve-dispatch",
            },
        )
    else:
        _log_voice_event(
            "mic-run",
            "dispatch_result",
            transcript=transcript,
            details=_dispatch_log_details(dispatch, approved=True, agent_id=agent_id),
        )
        if speech is None:
            _log_voice_event(
                "mic-run",
                "speech_decision",
                status="skipped",
                details={"spoken": False, "reason": "missing --speak-result"},
            )
        else:
            _log_voice_event(
                "mic-run",
                "speech_result",
                details={"adapter": speech["adapter"], "spoken": True},
            )

    recording = {
        "path": str(handle.path),
        "recorder": resolved_recorder,
        "requested_duration_seconds": duration,
        "file_kept": keep_file,
        **wav_metadata,
    }
    if as_json:
        output_data: dict[str, Any] = {
            "recording": recording,
            "transcription": transcription,
            "preview": preview,
        }
        if dispatch is None:
            output_data["dispatch_skipped"] = True
            output_data["dispatch_reason"] = "missing --approve-dispatch"
        else:
            output_data["dispatch"] = dispatch
        if speech is None:
            output_data["speech_skipped"] = True
            output_data["speech_reason"] = "missing --speak-result"
        else:
            output_data["speech"] = speech
        _emit_json(output_data)
        return

    click.echo("Microphone run")
    click.echo(f"  recorder: {resolved_recorder}")
    click.echo(f"  requested_duration_seconds: {duration}")
    click.echo(f"  path: {handle.path}")
    click.echo(f"  file_kept: {keep_file}")
    click.echo(f"  adapter: {transcription.get('backend') or adapter_id}")
    if transcription.get("language"):
        click.echo(f"  language: {transcription['language']}")
    click.echo(f"  transcript: {transcript}")
    _format_preview(preview)
    if dispatch is None:
        click.echo("  dispatch: skipped (pass --approve-dispatch to run)")
        click.echo("  speech: skipped (pass --speak-result after dispatch)")
        return
    _format_dispatch(dispatch)
    if speech is None:
        click.echo("  speech: skipped (pass --speak-result to speak dispatch result)")
    else:
        click.echo(f"  speech: spoken (adapter={speech['adapter']})")


@voice.command("capture-preview")
@click.option(
    "--duration",
    type=click.FloatRange(min=0.1),
    default=None,
    help=(
        "Recording duration in seconds; required unless "
        "[voice_control].default_record_duration is set."
    ),
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory for the recorded WAV. Defaults to the system temp directory.",
)
@click.option(
    "--recorder",
    "recorder_kind",
    type=click.Choice(RECORDER_KINDS),
    default=None,
    help=(
        "Local recorder implementation. Defaults to "
        "[voice_control].default_recorder or dev-silent."
    ),
)
@click.option(
    "--input-device",
    default=":0",
    show_default=True,
    help="macOS avfoundation input device for --recorder macos.",
)
@click.option(
    "--adapter",
    type=click.Choice(LOCAL_TRANSCRIPTION_ADAPTERS),
    default=None,
    help=(
        "Local transcription adapter to use. If omitted, [speech].backend must "
        "be explicitly set to a local adapter."
    ),
)
@click.option("--language", default=None, help="Optional language code hint.")
@click.option(
    "--session-id",
    default="",
    help="Optional client-side session id for the preview request.",
)
@click.option(
    "--base-url",
    envvar="OPENJARVIS_BASE_URL",
    default=None,
    help="OpenJarvis API base URL. Defaults to configured local server.",
)
@click.option(
    "--api-key",
    envvar="OPENJARVIS_API_KEY",
    default=None,
    help="API key for an authenticated local server.",
)
@click.option(
    "--timeout",
    default=10.0,
    show_default=True,
    help="HTTP timeout seconds.",
)
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON response.")
def capture_preview(
    duration: float | None,
    output_dir: Path | None,
    recorder_kind: str | None,
    input_device: str,
    adapter: str | None,
    language: str | None,
    session_id: str,
    base_url: str | None,
    api_key: str | None,
    timeout: float,
    as_json: bool,
) -> None:
    """Record, transcribe, and submit a preview; never dispatch automatically."""
    resolved_duration = _record_duration(duration)
    resolved_recorder = _configured_recorder_kind(recorder_kind)
    adapter_id, transcriber = _build_transcriber(adapter)

    if not as_json:
        click.echo("Voice capture preview")
        click.echo(
            f"  stage: recording local WAV "
            f"(recorder={resolved_recorder}, duration={resolved_duration:g}s)"
        )

    handle = _record_local_audio(
        duration=resolved_duration,
        output_dir=output_dir,
        recorder_kind=resolved_recorder,
        input_device=input_device,
    )

    if not as_json:
        click.echo(f"    path: {handle.path}")
        click.echo(f"  stage: transcribing local WAV (adapter={adapter_id})")

    try:
        transcription = transcriber.transcribe_file(handle.path, language=language)
    except (OSError, TranscriptionUnavailableError) as exc:
        raise click.ClickException(str(exc)) from exc
    transcription = transcription.to_dict()
    transcript = str(transcription.get("text") or "")

    if not as_json:
        if transcription.get("language"):
            click.echo(f"    language: {transcription['language']}")
        click.echo(f"    transcript: {transcript}")
        click.echo("  stage: submitting transcript preview")

    preview = _post_json(
        "/v1/voice/ptt/submit-transcript",
        {"transcript": transcript, "session_id": session_id},
        base_url=_base_url(base_url),
        api_key=_api_key(api_key),
        timeout=timeout,
    )
    preview_details = _preview_log_details(preview)
    preview_details.update(
        {
            "recording_path": str(handle.path),
            "recorder": resolved_recorder,
            "duration": resolved_duration,
            "adapter": adapter_id,
            "language": transcription.get("language") or "",
            "dispatch_skipped": True,
            "dispatch_reason": "capture-preview does not dispatch",
        }
    )
    _log_voice_event(
        "capture-preview",
        "preview_result",
        transcript=transcript,
        details=preview_details,
    )

    if as_json:
        _emit_json(
            {
                "recording": {
                    "path": str(handle.path),
                    "recorder": resolved_recorder,
                    "duration": resolved_duration,
                },
                "transcription": transcription,
                "preview": preview,
                "dispatch_skipped": True,
                "dispatch_reason": "capture-preview does not dispatch",
            }
        )
        return

    _format_preview(preview)
    click.echo("  dispatch: skipped (use `jarvis voice submit --approve-dispatch`)")


@voice.command("run-local")
@click.option(
    "--duration",
    type=click.FloatRange(min=0.1),
    default=None,
    help=(
        "Recording duration in seconds; required unless "
        "[voice_control].default_record_duration is set."
    ),
)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Directory for the recorded WAV. Defaults to the system temp directory.",
)
@click.option(
    "--recorder",
    "recorder_kind",
    type=click.Choice(RECORDER_KINDS),
    default=None,
    help=(
        "Local recorder implementation. Defaults to "
        "[voice_control].default_recorder or dev-silent."
    ),
)
@click.option(
    "--input-device",
    default=":0",
    show_default=True,
    help="macOS avfoundation input device for --recorder macos.",
)
@click.option(
    "--adapter",
    type=click.Choice(LOCAL_TRANSCRIPTION_ADAPTERS),
    default=None,
    help=(
        "Local transcription adapter to use. If omitted, [speech].backend must "
        "be explicitly set to a local adapter."
    ),
)
@click.option("--language", default=None, help="Optional language code hint.")
@click.option(
    "--session-id",
    default="",
    help="Optional client-side session id for the preview request.",
)
@click.option("--agent-id", default="", help="Agent id to dispatch to after approval.")
@click.option(
    "--approve-dispatch",
    is_flag=True,
    default=False,
    help="Explicitly approve and call /dispatch after preview.",
)
@click.option(
    "--speak-result",
    is_flag=True,
    default=False,
    help="Speak the dispatch result through an explicit local speech-output adapter.",
)
@click.option(
    "--speech-adapter",
    type=click.Choice(LOCAL_SPEECH_OUTPUT_ADAPTERS),
    default=None,
    help="Explicit local speech-output adapter for --speak-result.",
)
@click.option(
    "--voice",
    "voice_name",
    default=None,
    help="Optional macOS say voice name for --speak-result.",
)
@click.option(
    "--rate",
    type=click.IntRange(min=80, max=500),
    default=None,
    help="Optional macOS say speaking rate for --speak-result.",
)
@click.option(
    "--base-url",
    envvar="OPENJARVIS_BASE_URL",
    default=None,
    help="OpenJarvis API base URL. Defaults to configured local server.",
)
@click.option(
    "--api-key",
    envvar="OPENJARVIS_API_KEY",
    default=None,
    help="API key for an authenticated local server.",
)
@click.option(
    "--timeout",
    default=10.0,
    show_default=True,
    help="HTTP timeout seconds.",
)
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON response.")
def run_local(
    duration: float | None,
    output_dir: Path | None,
    recorder_kind: str | None,
    input_device: str,
    adapter: str | None,
    language: str | None,
    session_id: str,
    agent_id: str,
    approve_dispatch: bool,
    speak_result: bool,
    speech_adapter: str | None,
    voice_name: str | None,
    rate: int | None,
    base_url: str | None,
    api_key: str | None,
    timeout: float,
    as_json: bool,
) -> None:
    """Record, transcribe, and preview locally; approved dispatch is opt-in."""
    if speak_result and not approve_dispatch:
        raise click.UsageError("--speak-result requires --approve-dispatch")

    resolved_duration = _record_duration(duration)
    resolved_recorder = _configured_recorder_kind(recorder_kind)
    adapter_id, transcriber = _build_transcriber(adapter)
    resolved_base = _base_url(base_url)
    resolved_key = _api_key(api_key)

    if not as_json:
        click.echo("Voice local run")
        click.echo(
            f"  stage: recording local WAV "
            f"(recorder={resolved_recorder}, duration={resolved_duration:g}s)"
        )

    handle = _record_local_audio(
        duration=resolved_duration,
        output_dir=output_dir,
        recorder_kind=resolved_recorder,
        input_device=input_device,
    )

    if not as_json:
        click.echo(f"    path: {handle.path}")
        click.echo(f"  stage: transcribing local WAV (adapter={adapter_id})")

    try:
        transcription = transcriber.transcribe_file(handle.path, language=language)
    except (OSError, TranscriptionUnavailableError) as exc:
        raise click.ClickException(str(exc)) from exc
    transcription_data = transcription.to_dict()
    transcript = str(transcription_data.get("text") or "")

    if not as_json:
        if transcription_data.get("language"):
            click.echo(f"    language: {transcription_data['language']}")
        click.echo(f"    transcript: {transcript}")
        click.echo("  stage: submitting transcript preview")

    preview = _post_json(
        "/v1/voice/ptt/submit-transcript",
        {"transcript": transcript, "session_id": session_id},
        base_url=resolved_base,
        api_key=resolved_key,
        timeout=timeout,
    )
    run_details = _preview_log_details(preview)
    run_details.update(
        {
            "recording_path": str(handle.path),
            "recorder": resolved_recorder,
            "duration": resolved_duration,
            "adapter": adapter_id,
            "language": transcription_data.get("language") or "",
        }
    )
    _log_voice_event(
        "run-local",
        "preview_result",
        transcript=transcript,
        details=run_details,
    )

    dispatch: dict[str, Any] | None = None
    speech: dict[str, Any] | None = None
    if approve_dispatch:
        if not as_json:
            _format_preview(preview)
            click.echo("  stage: dispatching approved transcript")
        dispatch = _post_json(
            "/v1/voice/ptt/dispatch",
            {"transcript": transcript, "agent_id": agent_id, "approved": True},
            base_url=resolved_base,
            api_key=resolved_key,
            timeout=timeout,
        )
        _log_voice_event(
            "run-local",
            "dispatch_result",
            transcript=transcript,
            details=_dispatch_log_details(
                dispatch,
                approved=True,
                agent_id=agent_id,
            ),
        )
        if speak_result:
            speech_text = _dispatch_speech_text(dispatch)
            resolved_speech_adapter = _speech_output_adapter(speech_adapter)
            output = _build_speech_output(
                resolved_speech_adapter,
                voice_name=_speech_voice(voice_name),
                rate=_speech_rate(rate),
            )
            try:
                output.speak(speech_text)
            except (OSError, SpeechOutputUnavailableError, ValueError) as exc:
                raise click.ClickException(str(exc)) from exc
            speech = {"adapter": resolved_speech_adapter, "spoken": True}
            _log_voice_event(
                "run-local",
                "speech_result",
                transcript=speech_text,
                details={"adapter": resolved_speech_adapter, "spoken": True},
            )
    elif not as_json:
        _format_preview(preview)

    if dispatch is None:
        _log_voice_event(
            "run-local",
            "dispatch_decision",
            status="skipped",
            transcript=transcript,
            details={
                "approved": False,
                "attempted": False,
                "reason": "missing --approve-dispatch",
            },
        )
    elif speech is None:
        _log_voice_event(
            "run-local",
            "speech_decision",
            status="skipped",
            details={"spoken": False, "reason": "missing --speak-result"},
        )

    if as_json:
        output_data: dict[str, Any] = {
            "recording": {
                "path": str(handle.path),
                "recorder": resolved_recorder,
                "duration": resolved_duration,
            },
            "transcription": transcription_data,
            "preview": preview,
        }
        if dispatch is None:
            output_data["dispatch_skipped"] = True
            output_data["dispatch_reason"] = "missing --approve-dispatch"
        else:
            output_data["dispatch"] = dispatch
        if speech is None:
            output_data["speech_skipped"] = True
            output_data["speech_reason"] = "missing --speak-result"
        else:
            output_data["speech"] = speech
        _emit_json(output_data)
        return

    if dispatch is None:
        click.echo("  dispatch: skipped (pass --approve-dispatch to run)")
        click.echo("  speech: skipped (pass --speak-result after dispatch)")
        return

    _format_dispatch(dispatch)
    if speech is None:
        click.echo("  speech: skipped (pass --speak-result to speak dispatch result)")
    else:
        click.echo(f"  speech: spoken (adapter={speech['adapter']})")


@voice.command("logs")
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    default=20,
    show_default=True,
    help="Number of recent voice events to show.",
)
@click.option(
    "--event",
    "event_types",
    multiple=True,
    help="Show only events with this exact event type. May be repeated.",
)
@click.option(
    "--status",
    "statuses",
    multiple=True,
    help="Show only events with this exact status. May be repeated.",
)
@click.option("--success", is_flag=True, help="Show successful events only.")
@click.option("--failure", is_flag=True, help="Show failed events only.")
@click.option(
    "--approval-dispatch-only",
    is_flag=True,
    help="Show only approval or dispatch-related events.",
)
@click.option("--json", "as_json", is_flag=True, help="Print JSON events.")
@click.option(
    "--export",
    "export_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Write filtered events to a local export file.",
)
@click.option(
    "--export-format",
    type=click.Choice(["auto", "jsonl", "json"]),
    default="auto",
    show_default=True,
    help="Export format. Auto uses .json for JSON and JSONL otherwise.",
)
@click.option(
    "--clear",
    "clear_all",
    is_flag=True,
    help="Clear all local voice log events. Requires --confirm unless --dry-run.",
)
@click.option(
    "--clear-before",
    default=None,
    metavar="YYYY-MM-DD",
    help=(
        "Clear local voice log events before this UTC date. Requires --confirm "
        "unless --dry-run."
    ),
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview a cleanup without changing the local voice log.",
)
@click.option(
    "--confirm",
    is_flag=True,
    help="Confirm a destructive local voice log cleanup.",
)
def logs(
    limit: int,
    event_types: tuple[str, ...],
    statuses: tuple[str, ...],
    success: bool,
    failure: bool,
    approval_dispatch_only: bool,
    as_json: bool,
    export_path: Path | None,
    export_format: str,
    clear_all: bool,
    clear_before: str | None,
    dry_run: bool,
    confirm: bool,
) -> None:
    """Show or explicitly clean up local structured voice command events."""
    if success and failure:
        raise click.UsageError("--success and --failure are mutually exclusive")
    cutoff = _parse_voice_logs_clear_before(clear_before)
    cleanup_requested = clear_all or cutoff is not None
    if clear_all and cutoff is not None:
        raise click.UsageError("--clear and --clear-before are mutually exclusive")
    if cleanup_requested and export_path is not None:
        raise click.UsageError("--export cannot be combined with log cleanup")

    logger = _voice_event_logger()
    if cleanup_requested:
        refused = not dry_run and not confirm
        try:
            cleanup = cleanup_voice_events(
                logger.path,
                clear_all=clear_all,
                clear_before=cutoff,
                dry_run=True if refused else dry_run,
            )
        except OSError as exc:
            raise click.ClickException(f"Could not clean up voice logs: {exc}") from exc
        if as_json:
            output = {
                "enabled": logger.enabled,
                "path": str(logger.path) if logger.path else "",
                "cleanup": cleanup.to_dict()
                | {
                    "requested": True,
                    "confirmed": confirm,
                    "refused": refused,
                    "mode": "clear" if clear_all else "clear-before",
                },
            }
            _emit_json(output)
            if refused:
                raise click.exceptions.Exit(1)
            return

        click.echo("Voice log cleanup")
        click.echo(f"  enabled: {logger.enabled}")
        click.echo(f"  path: {logger.path if logger.path else '-'}")
        click.echo(f"  mode: {'clear' if clear_all else 'clear-before'}")
        if clear_before:
            click.echo(f"  clear_before: {clear_before}")
        if refused:
            click.echo("  refused: pass --confirm to delete local voice log events")
            raise click.exceptions.Exit(1)
        click.echo(f"  dry_run: {cleanup.dry_run}")
        click.echo(f"  matched_for_delete: {cleanup.deleted_count}")
        click.echo(f"  kept: {cleanup.kept_count}")
        if cleanup.dry_run:
            click.echo("  changed: false")
        else:
            click.echo(f"  changed: {str(cleanup.changed).lower()}")
        return

    events = query_voice_events(
        logger.path,
        limit=limit,
        event_types=event_types,
        statuses=statuses,
        success=False if failure else True if success else None,
        approval_dispatch_only=approval_dispatch_only,
    )
    exported_format = ""
    if export_path is not None:
        exported_format = _voice_logs_export_format(export_path, export_format)
        _write_voice_logs_export(
            events=events,
            path=export_path,
            output_format=exported_format,
        )
    if as_json:
        output: dict[str, Any] = {
            "enabled": logger.enabled,
            "path": str(logger.path) if logger.path else "",
            "filters": {
                "event_types": list(event_types),
                "statuses": list(statuses),
                "success": success,
                "failure": failure,
                "approval_dispatch_only": approval_dispatch_only,
                "limit": limit,
            },
            "events": events,
        }
        if export_path is not None:
            output["export"] = {
                "path": str(export_path),
                "format": exported_format,
                "count": len(events),
            }
        _emit_json(output)
        return

    click.echo("Voice logs")
    click.echo(f"  enabled: {logger.enabled}")
    click.echo(f"  path: {logger.path if logger.path else '-'}")
    if export_path is not None:
        click.echo(
            f"  export: wrote {len(events)} event(s) to {export_path}"
            f" ({exported_format})"
        )
    if event_types:
        click.echo(f"  event_filter: {', '.join(event_types)}")
    if statuses:
        click.echo(f"  status_filter: {', '.join(statuses)}")
    if success:
        click.echo("  success_filter: true")
    if failure:
        click.echo("  failure_filter: true")
    if approval_dispatch_only:
        click.echo("  approval_dispatch_only: true")
    if not events:
        click.echo("  no voice events logged")
        return

    for event in events:
        transcript = event.get("transcript") or {}
        transcript_info = ""
        if transcript:
            transcript_info = (
                f" transcript_length={transcript.get('length', 0)}"
                f" transcript_sha256={str(transcript.get('sha256', ''))[:12]}"
            )
        click.echo(
            "  "
            f"{event.get('timestamp', '-')}"
            f" {event.get('command', '-')}"
            f" {event.get('event', '-')}"
            f" status={event.get('status', '-')}"
            f"{transcript_info}"
        )


@voice.command("cancel")
@click.option(
    "--base-url",
    envvar="OPENJARVIS_BASE_URL",
    default=None,
    help="OpenJarvis API base URL. Defaults to configured local server.",
)
@click.option(
    "--api-key",
    envvar="OPENJARVIS_API_KEY",
    default=None,
    help="API key for an authenticated local server.",
)
@click.option(
    "--timeout",
    default=10.0,
    show_default=True,
    help="HTTP timeout seconds.",
)
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON response.")
def cancel(
    base_url: str | None,
    api_key: str | None,
    timeout: float,
    as_json: bool,
) -> None:
    """Cancel the current manual voice session."""
    data = _post_json(
        "/v1/voice/ptt/cancel",
        {},
        base_url=_base_url(base_url),
        api_key=_api_key(api_key),
        timeout=timeout,
    )
    _log_voice_event(
        "cancel",
        "cancel_result",
        details={
            "status": data.get("status", ""),
            "fsm_state": data.get("fsm_state", ""),
        },
    )
    if as_json:
        _emit_json(data)
    else:
        click.echo(f"Voice session fsm_state: {data.get('fsm_state', '-')}")


@voice.command("status")
@click.option(
    "--base-url",
    envvar="OPENJARVIS_BASE_URL",
    default=None,
    help="OpenJarvis API base URL. Defaults to configured local server.",
)
@click.option(
    "--api-key",
    envvar="OPENJARVIS_API_KEY",
    default=None,
    help="API key for an authenticated local server.",
)
@click.option(
    "--timeout",
    default=10.0,
    show_default=True,
    help="HTTP timeout seconds.",
)
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON response.")
def status(
    base_url: str | None,
    api_key: str | None,
    timeout: float,
    as_json: bool,
) -> None:
    """Show push-to-talk and manual session state."""
    data = _get_json(
        "/v1/voice/ptt/status",
        base_url=_base_url(base_url),
        api_key=_api_key(api_key),
        timeout=timeout,
    )
    _log_voice_event(
        "status",
        "status_result",
        details={
            "fsm_state": data.get("fsm_state", ""),
            "push_to_talk_only": data.get("push_to_talk_only", True),
            "passive_listening": data.get("passive_listening", False),
        },
    )
    if as_json:
        _emit_json(data)
    else:
        click.echo("Voice status")
        click.echo(f"  fsm_state: {data.get('fsm_state', '-')}")
        click.echo(f"  push_to_talk_only: {data.get('push_to_talk_only', True)}")
        click.echo(f"  passive_listening: {data.get('passive_listening', False)}")
