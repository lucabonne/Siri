"""``jarvis voice`` - explicit local/manual voice bridge commands."""

from __future__ import annotations

import json
import os
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
from openjarvis.hotkeys.macos_bridge import MacOSHotkeyBridgeCommand
from openjarvis.voice.event_log import (
    VoiceEventLogger,
    cleanup_voice_events,
    query_voice_events,
    voice_log_settings_from_config,
)
from openjarvis.voice.models import TranscriptionUnavailableError, VoiceRecordingError
from openjarvis.voice.recorder import (
    MICROPHONE_RECORDER_KINDS,
    RECORDER_KINDS,
    LocalMacOSRecorder,
    Recorder,
    SilentWavRecorder,
    SoundDeviceRecorder,
    inspect_wav_file,
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
            "mic-smoke requires a real microphone recorder. Pass --recorder "
            "macos or --recorder sounddevice, or configure one in "
            "[voice_control].default_recorder."
        )
    return configured


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
    recorder = data["recorder"]
    click.echo(
        "  recorder: "
        f"{recorder['configured_default']} "
        f"(supported={recorder['supported']}, "
        f"available={recorder['backend_available']})"
    )
    click.echo(f"  sounddevice_importable: {recorder['sounddevice_importable']}")
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


@click.group("voice")
def voice() -> None:
    """Explicit local/manual voice flow over /v1/voice/ptt."""


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
    type=click.FloatRange(min=0.1),
    default=None,
    help=(
        "Duration to include in the printed run-local command. Defaults to "
        "[voice_control].default_record_duration or 2.0."
    ),
)
@click.option(
    "--recorder",
    "recorder_kind",
    type=click.Choice(RECORDER_KINDS),
    default=None,
    help="Recorder to include in the printed run-local command.",
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
        "Local transcription adapter to include. If omitted, run-local still "
        "requires [speech].backend to be explicitly configured later."
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
) -> None:
    """Print a disabled macOS hotkey bridge command/example only."""
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
    bridge_format = output_format or getattr(
        defaults,
        "hotkey_bridge_format",
        "command",
    )
    if bridge_format not in {"command", "hammerspoon", "json"}:
        raise click.ClickException(f"unsupported hotkey bridge format: {bridge_format}")
    bridge_recorder = recorder_kind or getattr(
        defaults,
        "hotkey_bridge_recorder",
        "macos",
    )
    if bridge_recorder not in RECORDER_KINDS:
        raise click.ClickException(
            f"unsupported hotkey bridge recorder: {bridge_recorder}"
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
        click.echo(bridge.hammerspoon_snippet().rstrip())
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
def record_local(
    duration: float | None,
    output_dir: Path | None,
    recorder_kind: str | None,
    input_device: str,
) -> None:
    """Record to a local WAV file only; never transcribe or dispatch."""
    resolved_duration = _record_duration(duration)
    resolved_recorder = _configured_recorder_kind(recorder_kind)
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
    type=click.FloatRange(min=0.1, max=30.0),
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
    """Record and inspect a bounded microphone sample without further actions."""
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
    type=click.FloatRange(min=0.1, max=30.0),
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
    """Record and transcribe one bounded sample without API or speech actions."""
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
    help="Speak the dispatch result through an explicit local TTS adapter.",
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
    """Run the explicit local voice pipeline; dispatch/TTS are opt-in."""
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
