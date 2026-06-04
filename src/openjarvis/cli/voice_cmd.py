"""``jarvis voice`` - local typed/mock voice bridge commands."""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

import click
import httpx

from openjarvis.core.config import load_config
from openjarvis.hotkeys.macos_bridge import MacOSHotkeyBridgeCommand
from openjarvis.voice.event_log import (
    VoiceEventLogger,
    query_voice_events,
    voice_log_settings_from_config,
)
from openjarvis.voice.models import TranscriptionUnavailableError, VoiceRecordingError
from openjarvis.voice.recorder import LocalMacOSRecorder, Recorder, SilentWavRecorder
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
    return SilentWavRecorder(temp_dir=output_dir)


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
    """Local typed/mock voice flow over /v1/voice/ptt."""


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
    type=click.Choice(["dev-silent", "macos"]),
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
    if bridge_recorder not in {"dev-silent", "macos"}:
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
    type=click.Choice(["dev-silent", "macos"]),
    default="dev-silent",
    show_default=True,
    help="Local recorder implementation.",
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
    recorder_kind: str,
    input_device: str,
) -> None:
    """Record to a local WAV file only; never transcribe or dispatch."""
    resolved_duration = _record_duration(duration)
    recorder = _build_recorder(
        recorder_kind,
        output_dir=output_dir,
        input_device=input_device,
    )
    handle = recorder.start(uuid.uuid4().hex)
    try:
        _sleep(resolved_duration)
    finally:
        recorder.stop(handle)
    _log_voice_event(
        "record-local",
        "recording_result",
        details={
            "path": str(handle.path),
            "recorder": recorder_kind,
            "duration": resolved_duration,
            "transcribed": False,
            "dispatch_skipped": True,
        },
    )
    click.echo(str(handle.path))


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
    type=click.Choice(["dev-silent", "macos"]),
    default="dev-silent",
    show_default=True,
    help="Local recorder implementation.",
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
    recorder_kind: str,
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
    adapter_id, transcriber = _build_transcriber(adapter)
    recorder = _build_recorder(
        recorder_kind,
        output_dir=output_dir,
        input_device=input_device,
    )

    if not as_json:
        click.echo("Voice capture preview")
        click.echo(
            f"  stage: recording local WAV "
            f"(recorder={recorder_kind}, duration={resolved_duration:g}s)"
        )

    handle = recorder.start(uuid.uuid4().hex)
    try:
        _sleep(resolved_duration)
    finally:
        recorder.stop(handle)

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
            "recorder": recorder_kind,
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
                    "recorder": recorder_kind,
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
    type=click.Choice(["dev-silent", "macos"]),
    default="dev-silent",
    show_default=True,
    help="Local recorder implementation.",
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
    recorder_kind: str,
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
    adapter_id, transcriber = _build_transcriber(adapter)
    resolved_base = _base_url(base_url)
    resolved_key = _api_key(api_key)

    if not as_json:
        click.echo("Voice local run")
        click.echo(
            f"  stage: recording local WAV "
            f"(recorder={recorder_kind}, duration={resolved_duration:g}s)"
        )

    handle = _record_local_audio(
        duration=resolved_duration,
        output_dir=output_dir,
        recorder_kind=recorder_kind,
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
            "recorder": recorder_kind,
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
                "recorder": recorder_kind,
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
def logs(
    limit: int,
    event_types: tuple[str, ...],
    statuses: tuple[str, ...],
    success: bool,
    failure: bool,
    approval_dispatch_only: bool,
    as_json: bool,
) -> None:
    """Show recent local structured voice command events."""
    if success and failure:
        raise click.UsageError("--success and --failure are mutually exclusive")

    logger = _voice_event_logger()
    events = query_voice_events(
        logger.path,
        limit=limit,
        event_types=event_types,
        statuses=statuses,
        success=False if failure else True if success else None,
        approval_dispatch_only=approval_dispatch_only,
    )
    if as_json:
        _emit_json(
            {
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
        )
        return

    click.echo("Voice logs")
    click.echo(f"  enabled: {logger.enabled}")
    click.echo(f"  path: {logger.path if logger.path else '-'}")
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
    """Cancel the current typed/mock voice session."""
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
    """Show push-to-talk and typed/mock session state."""
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
