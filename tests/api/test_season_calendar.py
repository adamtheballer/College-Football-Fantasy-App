from __future__ import annotations

from hashlib import sha256

import pytest

from collegefootballfantasy_api.app.services.power4 import list_playoff_eligible_schools
from collegefootballfantasy_api.app.services.season_calendar import (
    SEALED_SCHEDULE_FORMAT_VERSION,
    SeasonCalendarCoverageError,
    SealedScheduleRow,
    SealedScheduleSnapshot,
    certification_report,
    certify_season_calendar,
)


def _snapshot(*, weeks=(11, 12, 13), excluded=(), duplicate=False) -> SealedScheduleSnapshot:
    rows = []
    excluded_set = set(excluded)
    schools = list_playoff_eligible_schools()
    for week in weeks:
        for index, school in enumerate(schools):
            if (school, week) in excluded_set:
                continue
            rows.append(SealedScheduleRow(team=school, week=week, opponent=f"Opponent {index}", location="home"))
    if duplicate:
        rows.append(SealedScheduleRow(team=schools[0], week=13, opponent="Contradiction", location="away"))
    return SealedScheduleSnapshot(
        season=2026,
        source_identity="test:2026-snapshot",
        source_revision="test-revision",
        source_sha256=sha256(b"test").hexdigest(),
        format_version=SEALED_SCHEDULE_FORMAT_VERSION,
        rows=tuple(rows),
    )


@pytest.mark.parametrize(
    ("playoff_teams", "regular_end", "start", "championship"),
    [(2, 12, 13, 13), (4, 11, 12, 13), (6, 10, 11, 13), (8, 10, 11, 13)],
)
def test_2026_full_coverage_calendar_uses_the_latest_valid_windows(playoff_teams, regular_end, start, championship):
    calendar = certify_season_calendar(_snapshot(), playoff_teams)

    assert calendar.regular_season_end_week == regular_end
    assert calendar.playoff_start_week == start
    assert calendar.championship_week == championship
    assert calendar.max_rounds == {2: 1, 4: 2, 6: 3, 8: 3}[playoff_teams]


def test_calendar_rejects_a_bye_or_missing_school_in_required_window():
    school = list_playoff_eligible_schools()[0]
    snapshot = _snapshot(weeks=(13,), excluded=[(school, 13)])

    with pytest.raises(SeasonCalendarCoverageError, match="no contiguous"):
        certify_season_calendar(snapshot, 2)


def test_calendar_rejects_duplicate_or_contradictory_team_week_evidence():
    with pytest.raises(SeasonCalendarCoverageError, match="duplicate"):
        certify_season_calendar(_snapshot(duplicate=True), 2)


def test_calendar_ignores_conference_title_bowl_and_cfp_rows():
    base = _snapshot()
    invalid_rows = tuple(
        SealedScheduleRow(team=school, week=14, opponent="Opponent", location="neutral", game_kind="conference_championship")
        for school in list_playoff_eligible_schools()
    )

    calendar = certify_season_calendar(
        SealedScheduleSnapshot(**{**base.__dict__, "rows": base.rows + invalid_rows}),
        2,
    )

    assert calendar.championship_week == 13


def test_certification_report_exposes_provenance_and_selected_windows():
    report = certification_report(_snapshot())

    assert report["status"] == "certified"
    assert report["eligible_school_count"] == len(list_playoff_eligible_schools())
    assert report["selected_windows"] == {
        "2": {"playoff_start_week": 13, "championship_week": 13, "regular_season_end_week": 12, "rounds": 1},
        "4": {"playoff_start_week": 12, "championship_week": 13, "regular_season_end_week": 11, "rounds": 2},
        "6": {"playoff_start_week": 11, "championship_week": 13, "regular_season_end_week": 10, "rounds": 3},
        "8": {"playoff_start_week": 11, "championship_week": 13, "regular_season_end_week": 10, "rounds": 3},
    }
