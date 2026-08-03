#!/usr/bin/env python3
"""Emit the immutable source versions that identify a beta runtime.

Only committed source artifacts are read. The current CFB27 data is an
application-managed JSON export rather than a Google Sheet manifest, so its
content hash identifies the exact ratings loaded by this runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


HEX = re.compile(r"^[a-f0-9]{64}$")


def version_for(manifest: dict[str, object], source_name: str) -> str:
    season = manifest.get("season")
    sources = manifest.get("sources")
    source = sources.get(source_name) if isinstance(sources, dict) else None
    if not isinstance(source, dict):
        raise ValueError(f"source manifest is missing {source_name!r} metadata")
    digest = source.get("sha256")
    if not isinstance(season, int) or not isinstance(digest, str) or not HEX.fullmatch(digest):
        raise ValueError(f"source manifest has an invalid {source_name!r} season or sha256")
    return f"{season}:{digest[:12]}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default="reports/source-imports/2026")
    parser.add_argument("--shell", action="store_true")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    manifest = json.loads((source_dir / "source-manifest.json").read_text(encoding="utf-8"))
    rating_digest = hashlib.sha256(Path("api/app/data/cfb27_ratings.json").read_bytes()).hexdigest()

    values = {
        "CFF_PLAYER_DATASET_VERSION": version_for(manifest, "identity"),
        "CFF_PROJECTION_DATASET_VERSION": version_for(manifest, "projection"),
        "CFF_CFB27_RATING_DATASET_VERSION": f"2026:{rating_digest[:12]}",
    }
    if args.shell:
        for name, value in values.items():
            print(f"export {name}={value!r}")
    else:
        print(json.dumps(values, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
