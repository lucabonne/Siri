#!/usr/bin/env python3
"""Build the local Siri macOS app bundle."""

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
    parser = argparse.ArgumentParser(description="Build the Siri .app bundle")
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory that will receive Siri.app; defaults to build/packaging",
    )
    args = parser.parse_args()

    service = PackagingService(project_root=ROOT)
    result = service.build_app_bundle(output_dir=args.output_dir or None)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "built" else 1


if __name__ == "__main__":
    raise SystemExit(main())
