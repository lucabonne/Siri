"""Local-only client and discovery for optional WorldMonitor instances."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import httpx

LOCALHOST_URLS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
)


def is_localhost_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }


def candidate_repo_paths(cwd: str | Path | None = None) -> list[Path]:
    paths: list[Path] = []
    env_path = os.environ.get("WORLDMONITOR_REPO")
    if env_path:
        paths.append(Path(env_path).expanduser())
    roots = [
        Path(cwd).expanduser() if cwd else Path.cwd(),
        Path.home() / "Documents",
        Path.home() / "Code",
        Path.home() / "Developer",
    ]
    for root in roots:
        paths.extend(
            [
                root / "worldmonitor",
                root / "WorldMonitor",
                root / "koala73" / "worldmonitor",
            ]
        )
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def detect_local_repo(cwd: str | Path | None = None) -> Path | None:
    for path in candidate_repo_paths(cwd):
        if (path / "package.json").exists() and (
            (path / "api").exists() or (path / "src").exists()
        ):
            return path
    return None


class WorldMonitorClient:
    """Thin client for local WorldMonitor HTTP endpoints."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 2.0,
    ) -> None:
        if base_url and not is_localhost_url(base_url):
            raise ValueError("WorldMonitor integration only accepts localhost URLs")
        self.base_url = (base_url or "").rstrip("/")
        self.timeout_seconds = timeout_seconds

    def discover_base_url(self) -> str:
        if self.base_url and self.health(self.base_url):
            return self.base_url
        for url in LOCALHOST_URLS:
            if self.health(url):
                self.base_url = url
                return url
        return self.base_url

    def health(self, base_url: str | None = None) -> bool:
        url = (base_url or self.base_url).rstrip("/")
        if not url or not is_localhost_url(url):
            return False
        for path in ("/api/health", "/api/version", "/api/bootstrap"):
            try:
                response = httpx.get(
                    f"{url}{path}",
                    timeout=self.timeout_seconds,
                    follow_redirects=True,
                )
                if response.status_code < 500:
                    return True
            except httpx.HTTPError:
                continue
        return False

    def fetch_bootstrap(self) -> dict:
        base_url = self.discover_base_url()
        if not base_url:
            return {}
        try:
            response = httpx.get(
                f"{base_url}/api/bootstrap",
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}
        except (httpx.HTTPError, ValueError):
            return {}


__all__ = [
    "LOCALHOST_URLS",
    "WorldMonitorClient",
    "detect_local_repo",
    "is_localhost_url",
]
