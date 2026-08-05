from __future__ import annotations

from scripts.import_google_historical_season_stats import (
    VERIFIED_SOURCE_NAME_ALIASES,
    SourceSeasonRow,
    _assign_row,
    _identity_key,
    _resolve_player,
    build_report,
    read_source_rows,
)
from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
from datetime import datetime, timezone


class PlayerStub:
    def __init__(self, player_id: int, name: str, school: str, position: str):
        self.id = player_id
        self.name = name
        self.school = school
        self.position = position


def test_reads_header_after_sheet_title_and_preserves_source_values(tmp_path):
    source = tmp_path / "season-stats.csv"
    source.write_text(
        "CFB PLAYER PREVIOUS STATS\n"
        "Updated weekly\n"
        "CURRENT TEAM,DEPTH POS,PLAYER,SEASON,COLLEGE TEAM,PASS CMP,REC,REC YDS,SOURCE URL\n"
        "Alabama,WR1,Example Receiver,2025,ALA,0,55,811,https://example.test/player/1\n",
        encoding="utf-8",
    )

    rows = read_source_rows(source)

    assert len(rows) == 1
    assert rows[0].row_number == 4
    assert rows[0].position == "WR"
    assert rows[0].receptions == 55
    assert rows[0].receiving_yards == 811


def test_resolves_only_exact_or_reviewed_alias_identity():
    source = SourceSeasonRow(
        row_number=4,
        current_team="UCLA",
        depth_position="WR4",
        player_name="Aidan Mizell",
        season=2025,
        college_team="UCLA",
        passing_completions=None,
        passing_attempts=None,
        passing_yards=None,
        passing_touchdowns=None,
        interceptions=None,
        rushing_attempts=None,
        rushing_yards=None,
        rushing_touchdowns=None,
        receptions=10,
        receiving_yards=99,
        receiving_touchdowns=None,
        field_goals_made=None,
        field_goals_attempted=None,
        extra_points_made=None,
        extra_points_attempted=None,
        kick_points=None,
        source_url=None,
    )
    player = PlayerStub(1, "Aiden Mizell", "UCLA", "WR")
    players = {_identity_key(player.name, player.school, player.position): player}

    resolved, match_type = _resolve_player(source, players)

    assert VERIFIED_SOURCE_NAME_ALIASES[source.identity_key] == "Aiden Mizell"
    assert resolved is player
    assert match_type == "verified_alias"


def test_resolves_approved_team_abbreviations_without_relaxing_identity():
    source = SourceSeasonRow(
        row_number=4,
        current_team="WVU",
        depth_position="TE2",
        player_name="Cameron Ball",
        season=2025,
        college_team="WVU",
        passing_completions=None,
        passing_attempts=None,
        passing_yards=None,
        passing_touchdowns=None,
        interceptions=None,
        rushing_attempts=None,
        rushing_yards=None,
        rushing_touchdowns=None,
        receptions=10,
        receiving_yards=99,
        receiving_touchdowns=None,
        field_goals_made=None,
        field_goals_attempted=None,
        extra_points_made=None,
        extra_points_attempted=None,
        kick_points=None,
        source_url=None,
    )
    player = PlayerStub(1, "Cam Ball", "West Virginia", "TE")
    players = {_identity_key(player.name, player.school, player.position): player}

    resolved, match_type = _resolve_player(source, players)

    assert resolved is player
    assert match_type == "verified_alias"


def test_import_assignment_persists_standard_fantasy_points():
    source = SourceSeasonRow(
        row_number=4,
        current_team="Georgia",
        depth_position="WR1",
        player_name="Example Receiver",
        season=2025,
        college_team="Georgia",
        passing_completions=0,
        passing_attempts=0,
        passing_yards=0,
        passing_touchdowns=0,
        interceptions=0,
        rushing_attempts=0,
        rushing_yards=0,
        rushing_touchdowns=0,
        receptions=55,
        receiving_yards=811,
        receiving_touchdowns=6,
        field_goals_made=None,
        field_goals_attempted=None,
        extra_points_made=None,
        extra_points_attempted=None,
        kick_points=None,
        source_url=None,
    )
    player = PlayerStub(1, "Example Receiver", "Georgia", "WR")
    historical = PlayerHistoricalSeasonStat(
        player_id=player.id,
        provider="google_season_stats",
        provider_player_id="canonical:1",
        season=2025,
        season_type="regular",
        parser_version="sheet-v1",
        imported_at=datetime.now(timezone.utc),
    )

    _assign_row(historical, source, player, {}, "source-hash", datetime.now(timezone.utc))

    assert historical.fantasy_points == 172.1
    assert historical.scoring_rules_version == "standard-full-ppr-v1"


def test_report_distinguishes_missing_history_from_missing_source_identity():
    player_with_no_college_season = PlayerStub(1, "New Freshman", "Texas", "WR")
    player_absent_from_source = PlayerStub(2, "Missing Player", "Texas", "WR")
    source = SourceSeasonRow(
        row_number=4,
        current_team="Texas",
        depth_position="WR4",
        player_name="New Freshman",
        season=0,
        college_team=None,
        passing_completions=None,
        passing_attempts=None,
        passing_yards=None,
        passing_touchdowns=None,
        interceptions=None,
        rushing_attempts=None,
        rushing_yards=None,
        rushing_touchdowns=None,
        receptions=None,
        receiving_yards=None,
        receiving_touchdowns=None,
        field_goals_made=None,
        field_goals_attempted=None,
        extra_points_made=None,
        extra_points_attempted=None,
        kick_points=None,
        source_url=None,
    )

    report = build_report([source], [player_with_no_college_season, player_absent_from_source])

    assert report["catalog_players_without_source_history_by_reason"] == {
        "source_has_no_completed_college_season": 1,
        "no_source_identity_row": 1,
    }
