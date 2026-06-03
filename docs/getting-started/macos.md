# macOS Install

```bash
curl -fsSL https://openjarvis.ai/install.sh | bash
```

Works on Intel and Apple Silicon. The installer auto-detects your CPU/GPU.

## Prerequisites

If you've never run `git` or `curl` on this Mac, macOS will prompt you to install the Xcode Command Line Tools the first time you run them. Accept the prompt; that gives you both.

If you'd rather pre-install:

```bash
xcode-select --install
```

## Apple Silicon notes

- The installer picks `mlx` as the recommended engine via the standard hardware-detect path, but the foreground default is still Ollama for compatibility. Switch later with `jarvis init --force` and pick `mlx` if you've installed `mlx-lm`.
- Unified memory is reported as "VRAM" by the installer — that's intentional; on Apple Silicon, system RAM is what GPU-accelerated models can use.

## Voice permissions

- Local microphone recording, when explicitly requested with `jarvis voice record-local --recorder macos`, `jarvis voice capture-preview --recorder macos`, or `jarvis voice run-local --recorder macos`, requires macOS **Microphone** permission.
- Local speech output, when explicitly requested with `jarvis voice speak "text"` or `jarvis voice run-local --speak-result`, uses the macOS `say` command if available. It does not enable automatic response playback.
- `jarvis voice hotkey-bridge` only prints the preview-only `jarvis voice run-local` command or a disabled Hammerspoon example that an external helper can call later. It does not start a global listener, capture Fn, record audio, dispatch, approve, or speak.
- Future Hammerspoon or Swift Fn/push-to-talk helpers will require macOS **Accessibility** permission for global hotkey capture. Any helper that invokes `jarvis voice run-local --recorder macos` will also require **Microphone** permission.
- OpenJarvis does not enable Fn capture, always-on listening, automatic dispatch, automatic speech playback, or voice-only mode in the current voice CLI.

## See also

- [Full installer reference](install.md)
