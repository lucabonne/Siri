# Siri App Bundle

This directory holds templates and notes for the local macOS `.app` bundle.

Generate a bundle with:

```sh
jarvis package build
```

The generated bundle is lightweight and local-only. Phase 1 intentionally does
not perform notarization, code signing, auto-updates, telemetry, or remote
installer work.
