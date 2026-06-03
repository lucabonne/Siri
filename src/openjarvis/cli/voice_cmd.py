"""``jarvis voice`` - local typed/mock voice bridge commands."""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import click
import httpx

from openjarvis.core.config import load_config
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


def _build_transcriber(
    adapter: str | None,
) -> tuple[str, SpeechBackendLocalTranscriptionAdapter]:
    config = load_config()
    try:
        adapter_id = resolve_local_transcription_adapter_id(
            requested_adapter=adapter,
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


@click.group("voice")
def voice() -> None:
    """Local typed/mock voice flow over /v1/voice/ptt."""


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

    if as_json:
        output: dict[str, Any] = {"preview": preview}
    else:
        _format_preview(preview)

    if not approve_dispatch:
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
    default="macos-say",
    show_default=True,
    help="Explicit local speech-output adapter.",
)
@click.option(
    "--voice",
    "voice_name",
    default="",
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
    adapter: str,
    voice_name: str,
    rate: int | None,
) -> None:
    """Speak text locally only when explicitly requested."""
    speech_text = " ".join(text).strip()
    if not speech_text:
        raise click.UsageError("text must not be empty")

    output = _build_speech_output(adapter, voice_name=voice_name, rate=rate)
    try:
        output.speak(speech_text)
    except (OSError, SpeechOutputUnavailableError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("Voice speech output")
    click.echo(f"  adapter: {adapter}")
    click.echo("  dispatch: skipped")


@voice.command("record-local")
@click.option(
    "--duration",
    required=True,
    type=click.FloatRange(min=0.1),
    help="Recording duration in seconds; required stop condition.",
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
    duration: float,
    output_dir: Path | None,
    recorder_kind: str,
    input_device: str,
) -> None:
    """Record to a local WAV file only; never transcribe or dispatch."""
    recorder = _build_recorder(
        recorder_kind,
        output_dir=output_dir,
        input_device=input_device,
    )
    handle = recorder.start(uuid.uuid4().hex)
    try:
        _sleep(duration)
    finally:
        recorder.stop(handle)
    click.echo(str(handle.path))


@voice.command("capture-preview")
@click.option(
    "--duration",
    required=True,
    type=click.FloatRange(min=0.1),
    help="Recording duration in seconds; required stop condition.",
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
    duration: float,
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
            f"(recorder={recorder_kind}, duration={duration:g}s)"
        )

    handle = recorder.start(uuid.uuid4().hex)
    try:
        _sleep(duration)
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

    if as_json:
        _emit_json(
            {
                "recording": {
                    "path": str(handle.path),
                    "recorder": recorder_kind,
                    "duration": duration,
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
    required=True,
    type=click.FloatRange(min=0.1),
    help="Recording duration in seconds; required stop condition.",
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
    default="macos-say",
    show_default=True,
    help="Explicit local speech-output adapter for --speak-result.",
)
@click.option(
    "--voice",
    "voice_name",
    default="",
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
    duration: float,
    output_dir: Path | None,
    recorder_kind: str,
    input_device: str,
    adapter: str | None,
    language: str | None,
    session_id: str,
    agent_id: str,
    approve_dispatch: bool,
    speak_result: bool,
    speech_adapter: str,
    voice_name: str,
    rate: int | None,
    base_url: str | None,
    api_key: str | None,
    timeout: float,
    as_json: bool,
) -> None:
    """Run the explicit local voice pipeline; dispatch/TTS are opt-in."""
    if speak_result and not approve_dispatch:
        raise click.UsageError("--speak-result requires --approve-dispatch")

    adapter_id, transcriber = _build_transcriber(adapter)
    resolved_base = _base_url(base_url)
    resolved_key = _api_key(api_key)

    if not as_json:
        click.echo("Voice local run")
        click.echo(
            f"  stage: recording local WAV "
            f"(recorder={recorder_kind}, duration={duration:g}s)"
        )

    handle = _record_local_audio(
        duration=duration,
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
        if speak_result:
            speech_text = _dispatch_speech_text(dispatch)
            output = _build_speech_output(
                speech_adapter,
                voice_name=voice_name,
                rate=rate,
            )
            try:
                output.speak(speech_text)
            except (OSError, SpeechOutputUnavailableError, ValueError) as exc:
                raise click.ClickException(str(exc)) from exc
            speech = {"adapter": speech_adapter, "spoken": True}
    elif not as_json:
        _format_preview(preview)

    if as_json:
        output_data: dict[str, Any] = {
            "recording": {
                "path": str(handle.path),
                "recorder": recorder_kind,
                "duration": duration,
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
        click.echo(f"  speech: spoken (adapter={speech_adapter})")


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
    if as_json:
        _emit_json(data)
    else:
        click.echo("Voice status")
        click.echo(f"  fsm_state: {data.get('fsm_state', '-')}")
        click.echo(f"  push_to_talk_only: {data.get('push_to_talk_only', True)}")
        click.echo(f"  passive_listening: {data.get('passive_listening', False)}")
