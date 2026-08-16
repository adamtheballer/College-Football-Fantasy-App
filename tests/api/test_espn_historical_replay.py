"""Deterministic replay of one sanitized, completed ESPN 2025 game.

The source fixture is captured once outside CI.  Tests never contact ESPN.
"""

from copy import deepcopy
import json
from pathlib import Path

from collegefootballfantasy_api.app.integrations.espn import extract_player_box_score_stats
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.services.espn_stats_sync import (
    normalize_espn_summary_player_stats,
    persist_normalized_espn_player_stats,
)
from collegefootballfantasy_api.app.services.scoring_service import calculate_player_fantasy_points, normalize_player_stats


FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "espn" / "2025-401752693-texas-san-jose-state.json"


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _player_rows(summary: dict) -> dict[str, dict]:
    return {row["PlayerName"]: row for row in extract_player_box_score_stats(summary)}


def _set_arch_passing_yards(summary: dict, value: int) -> None:
    for team in summary["boxscore"]["players"]:
        for category in team["statistics"]:
            if category["name"] != "passing":
                continue
            for athlete in category["athletes"]:
                if athlete["athlete"]["id"] == "4870906":
                    athlete["stats"][1] = str(value)
                    return
    raise AssertionError("historical fixture is missing Arch Manning's passing row")


def test_captured_2025_espn_fixture_replays_qb_rb_wr_te_and_kicker_with_canonical_rules():
    rows = _player_rows(_fixture())
    expected = {
        "Arch Manning": ("QB", 34.1),
        "CJ Baxter": ("RB", 8.1),
        "Parker Livingstone": ("WR", 28.8),
        "Jack Endries": ("TE", 19.2),
        "Mason Shipley": ("K", 12.0),
        "Denis Lynch": ("K", -1.0),
    }

    for name, (position, points) in expected.items():
        actual, _breakdown = calculate_player_fantasy_points(normalize_player_stats(rows[name], position), {}, position)
        assert actual == points

    # The only made FG is 47 yards, supplied exactly by ESPN's
    # `longFieldGoalMade`; it must land in the 41-50 tier, never flat 3.
    assert rows["Mason Shipley"]["fg_made_41_50"] == 1
    assert rows["Mason Shipley"]["espn_field_goal_distance_detail_available"] is True


def test_derived_cumulative_revisions_replace_not_add_and_identical_replay_is_idempotent(db_session):
    player = Player(name="Arch Manning", position="QB", school="Texas")
    db_session.add(player)
    db_session.flush()
    db_session.add(PlayerProviderId(player_id=player.id, provider="espn", provider_player_id="4870906", verification_status="verified"))
    db_session.commit()

    for yards in (80, 180, 295, 295):
        revision = deepcopy(_fixture())
        _set_arch_passing_yards(revision, yards)
        normalized, skipped = normalize_espn_summary_player_stats(
            db_session, season=2025, week=2, summary=revision, strict_identity=True
        )
        assert skipped == 5  # Fixture contains five other real ESPN athletes without test mappings.
        assert persist_normalized_espn_player_stats(db_session, season=2025, week=2, normalized_rows=normalized) == 1
        db_session.commit()
        stat = db_session.query(PlayerStat).filter_by(player_id=player.id, season=2025, week=2).one()
        assert stat.stats["pass_yards"] == float(yards)

    assert db_session.query(PlayerStat).filter_by(player_id=player.id, season=2025, week=2).count() == 1
