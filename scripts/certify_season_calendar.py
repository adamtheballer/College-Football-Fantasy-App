#!/usr/bin/env python3
"""Generate a release-reviewable certification from a sealed schedule artifact.

This command is read-only with respect to application data. It never contacts
an upstream provider and never imports its source into a database.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from collegefootballfantasy_api.app.services.season_calendar import (
    SeasonCalendarCoverageError,
    certification_report,
    load_sealed_schedule_snapshot,
)


def markdown(report: dict) -> str:
    lines = [
        f"# {report['season']} Fantasy Calendar Certification",
        "",
        f"- Status: **{report['status']}**",
        f"- Policy: `{report['calendar_policy_version']}`",
        f"- Source: `{report['source_identity']}` @ `{report['source_revision']}`",
        f"- Artifact SHA-256: `{report['source_sha256']}`",
        f"- Eligible schools: {report['eligible_school_count']}",
        "",
        "## Full-coverage windows",
        "",
        "- " + (", ".join(f"Weeks {start}–{end}" for start, end in report.get("contiguous_full_coverage_windows", [])) or "None"),
        "",
        "## Selected calendar",
        "",
        "| Playoff teams | Regular season ends | Playoffs | Championship | Rounds |",
        "| --- | --- | --- | --- | --- |",
    ]
    for count, selected in sorted(report.get("selected_windows", {}).items(), key=lambda item: int(item[0])):
        lines.append(
            f"| {count} | Week {selected['regular_season_end_week']} | Weeks {selected['playoff_start_week']}–{selected['championship_week']} | Week {selected['championship_week']} | {selected['rounds']} |"
        )
    if report.get("blocker"):
        lines.extend(["", "## Blocker", "", report["blocker"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Certify a sealed fantasy season calendar without provider or database access.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = certification_report(load_sealed_schedule_snapshot(args.season))
    except SeasonCalendarCoverageError as exc:
        report = {"season": args.season, "status": "blocked", "blocker": str(exc)}
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(markdown({
        "calendar_policy_version": "unavailable",
        "source_identity": "unavailable",
        "source_revision": "unavailable",
        "source_sha256": "unavailable",
        "eligible_school_count": 0,
        "contiguous_full_coverage_windows": [],
        "selected_windows": {},
        **report,
    }), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "certified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
