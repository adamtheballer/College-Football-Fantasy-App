from __future__ import annotations

from dataclasses import replace

import scripts.import_google_historical_season_stats as historical_import
from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from scripts.import_google_historical_season_stats import (
    VERIFIED_SOURCE_NAME_ALIASES,
    SourceSeasonRow,
    _canonical_fantasy_points,
    _identity_key,
    _resolve_player,
    build_report,
    read_source_rows,
)


def test_apply_deduplicates_one_trusted_espn_id_across_multiple_seasons(tmp_path, db_session, monkeypatch):
    """One athlete mapping must be inserted once even when history has many seasons."""
    player = Player(name="Example Runner", school="Example", position="RB")
    db_session.add(player)
    db_session.commit()
    player_id = player.id
    source = tmp_path / "season-stats.csv"
    source.write_text(
        "CURRENT TEAM,DEPTH POS,PLAYER,SEASON,COLLEGE TEAM,ESPN ID,GP\n"
        "Example,RB1,Example Runner,2024,Example,9999999,12\n"
        "Example,RB1,Example Runner,2025,Example,9999999,12\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(historical_import, "SessionLocal", lambda: db_session)

    report = historical_import.import_rows(source, apply=True)

    assert report["trusted_espn_id_conflict_count"] == 0
    assert report["provider_mappings_inserted"] == 1
    assert db_session.query(PlayerProviderId).filter_by(provider="espn", provider_player_id="9999999").count() == 1
    assert db_session.query(PlayerHistoricalSeasonStat).filter_by(player_id=player_id).count() == 2


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
        "CURRENT TEAM,DEPTH POS,PLAYER,SEASON,COLLEGE TEAM,PASS CMP,REC,REC YDS,ESPN ID,GP,SOURCE URL\n"
        "Alabama,WR1,Example Receiver,2025,ALA,0,55,811,12345,12,https://example.test/player/1\n",
        encoding="utf-8",
    )

    rows = read_source_rows(source)

    assert len(rows) == 1
    assert rows[0].row_number == 4
    assert rows[0].position == "WR"
    assert rows[0].receptions == 55
    assert rows[0].receiving_yards == 811
    assert rows[0].espn_player_id == "12345"
    assert rows[0].games_played == 12


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


def test_report_blocks_one_trusted_espn_id_attached_to_two_canonical_players():
    first = SourceSeasonRow(
        row_number=4,
        current_team="UCF",
        depth_position="WR1",
        player_name="First Receiver",
        season=2025,
        college_team="UCF",
        passing_completions=0,
        passing_attempts=0,
        passing_yards=0,
        passing_touchdowns=0,
        interceptions=0,
        rushing_attempts=0,
        rushing_yards=0,
        rushing_touchdowns=0,
        receptions=10,
        receiving_yards=100,
        receiving_touchdowns=1,
        field_goals_made=0,
        field_goals_attempted=0,
        extra_points_made=0,
        extra_points_attempted=0,
        kick_points=0,
        espn_player_id="1234567",
    )
    second = replace(
        first,
        row_number=5,
        current_team="Houston",
        player_name="Second Receiver",
        college_team="Houston",
    )
    players = [
        PlayerStub(1, "First Receiver", "UCF", "WR"),
        PlayerStub(2, "Second Receiver", "Houston", "WR"),
    ]

    report = build_report([first, second], players)

    assert report["trusted_espn_id_conflict_count"] == 1
    assert report["trusted_espn_id_conflicts"] == [
        {
            "provider": "espn",
            "provider_player_id": "1234567",
            "canonical_player_keys": ["firstreceiver|ucf|WR", "secondreceiver|houston|WR"],
            "reason": "one_trusted_espn_id_maps_to_multiple_canonical_players",
        }
    ]


def test_kicker_historical_totals_use_the_flat_beta_policy_without_distance_guessing():
    source = SourceSeasonRow(
        row_number=4,
        current_team="Example",
        depth_position="K",
        player_name="Example Kicker",
        season=2025,
        college_team="Example",
        passing_completions=0,
        passing_attempts=0,
        passing_yards=0,
        passing_touchdowns=0,
        interceptions=0,
        rushing_attempts=0,
        rushing_yards=0,
        rushing_touchdowns=0,
        receptions=0,
        receiving_yards=0,
        receiving_touchdowns=0,
        field_goals_made=22,
        field_goals_attempted=25,
        extra_points_made=30,
        extra_points_attempted=31,
        kick_points=None,
        source_url=None,
    )

    points, policy = _canonical_fantasy_points(source)

    assert points == 96
    assert policy == "component_stats_canonical_scoring_v2_beta_flat_kicker"
