"""Serve built Siri frontend assets with SPA fallback for local release smoke."""

from __future__ import annotations

import argparse
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


class SPAStaticHandler(BaseHTTPRequestHandler):
    directory: Path

    def do_GET(self) -> None:
        path = self._resolve_path()
        try:
            body = path.read_bytes()
        except OSError as exc:
            self.send_error(500, f"Unable to read static asset: {exc}")
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.send_header("cache-control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self) -> None:
        path = self._resolve_path()
        try:
            size = path.stat().st_size
        except OSError as exc:
            self.send_error(500, f"Unable to stat static asset: {exc}")
            return
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(size))
        self.send_header("cache-control", "no-cache")
        self.end_headers()

    def _resolve_path(self) -> Path:
        parsed = unquote(urlparse(self.path).path).lstrip("/")
        candidate = (self.directory / parsed).resolve()
        root = self.directory.resolve()
        if root in candidate.parents and candidate.is_file():
            return candidate
        return root / "index.html"

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.log_date_time_string()} {fmt % args}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the built Siri frontend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5173, type=int)
    parser.add_argument("--directory", required=True)
    args = parser.parse_args()

    directory = Path(args.directory).expanduser().resolve()
    if not (directory / "index.html").exists():
        raise SystemExit(f"static frontend index missing: {directory / 'index.html'}")
    os.chdir(directory)
    SPAStaticHandler.directory = directory
    server = ThreadingHTTPServer((args.host, args.port), SPAStaticHandler)
    print(f"Siri static frontend listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
