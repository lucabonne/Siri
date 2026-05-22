#!/usr/bin/env python3
"""Packaging-only command entry point for local macOS installer scripts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from openjarvis.packaging import PackagingService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the local Siri.app bundle")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install")
    install.add_argument("--destination", choices=["user", "system"], default="user")
    install.add_argument("--no-launch-agent", action="store_true")
    install.add_argument("--output-dir", default="")

    uninstall = subparsers.add_parser("uninstall")
    uninstall.add_argument(
        "--destination",
        choices=["user", "system", "all"],
        default="all",
    )
    uninstall.add_argument("--keep-launch-agent", action="store_true")

    subparsers.add_parser("release-diagnostics")

    args = parser.parse_args()
    service = PackagingService(project_root=ROOT)

    if args.command == "install":
        result = service.install_app_bundle(
            destination=args.destination,
            install_launch_agent=not args.no_launch_agent,
            output_dir=args.output_dir or None,
        )
    elif args.command == "uninstall":
        destinations = None if args.destination == "all" else [args.destination]
        result = service.uninstall_app_bundle(
            remove_launch_agent=not args.keep_launch_agent,
            destinations=destinations,
        )
    else:
        result = service.release_diagnostics()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
