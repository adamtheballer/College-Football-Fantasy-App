from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.domain.scoring_engine import calculate_player_fantasy_points
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.live_player_projection import LivePlayerProjection
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGameSnapshot
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.live_projection import (
    LIVE_PROJECTION_V1,
    persist_live_projections_for_snapshot,
    project_live_player,
    regulation_game_progress,
)


def _smith_prior():
    return {"receptions": 7, "rec_yards": 99, "rec_tds": 2, "targets": 10}


def _points(stats):
    return calculate_player_fantasy_points(stats, {"ppr": 1}, "WR")[0]


def test_jeremiah_smith_scoreless_first_quarter_regresses_toward_remaining_opportunity():
    result = project_live_player(
        pregame_stats=_smith_prior(), live_stats={}, position="WR", game_status="live", game_progress=0.25,
    )
    assert result.projection_status == "LIVE"
    assert 20 <= _points(result.projected_final_stats) <= 23
    assert _points(result.projected_final_stats) < _points(_smith_prior())


def test_kickoff_preserves_the_pregame_statline_until_live_evidence_arrives():
    result = project_live_player(
        pregame_stats=_smith_prior(), live_stats={}, position="WR", game_status="live", game_progress=0.0,
    )
    assert result.projection_status == "LIVE"
    assert _points(result.projected_final_stats) == pytest.approx(28.9)


def test_live_projection_uses_usage_without_extrapolating_touchdowns():
    under = project_live_player(
        pregame_stats=_smith_prior(), live_stats={"targets": 0}, position="WR", game_status="live", game_progress=0.5,
    )
    involved = project_live_player(
        pregame_stats=_smith_prior(), live_stats={"targets": 7, "receptions": 1, "rec_yards": 4}, position="WR", game_status="live", game_progress=0.5,
    )
    early_touchdown = project_live_player(
        pregame_stats=_smith_prior(), live_stats={"targets": 1, "receptions": 1, "rec_yards": 6, "rec_tds": 1}, position="WR", game_status="live", game_progress=0.25,
    )
    assert _points(involved.projected_final_stats) > _points(under.projected_final_stats)
    # The completed TD counts immediately, but the remaining TD prior is not
    # multiplied by the single early touchdown rate.
    assert early_touchdown.projected_remaining_stats["rec_tds"] <= 1.5


def test_overperformance_can_raise_a_projection_without_extrapolating_rates():
    result = project_live_player(
        pregame_stats=_smith_prior(),
        live_stats={"targets": 8, "receptions": 8, "rec_yards": 140, "rec_tds": 1},
        position="WR",
        game_status="live",
        game_progress=0.5,
    )
    assert _points(result.projected_final_stats) > 28.9
    assert result.projected_remaining_stats["rec_tds"] <= 1.0


def test_final_and_missing_clock_follow_explicit_safe_paths():
    final = project_live_player(
        pregame_stats=_smith_prior(), live_stats={"receptions": 5, "rec_yards": 80, "rec_tds": 1}, position="WR", game_status="final", game_progress=1.0,
    )
    stale = project_live_player(
        pregame_stats=_smith_prior(), live_stats={"receptions": 1}, position="WR", game_status="live", game_progress=None,
        previous_projection={"receptions": 6, "rec_yards": 85, "rec_tds": 1.2},
    )
    assert final.projection_status == "FINAL"
    assert final.projected_remaining_stats["rec_yards"] == 0
    assert stale.projection_status == "STALE"
    assert stale.fallback_reason == "missing_game_progress"
    assert stale.projected_final_stats["rec_yards"] == 85


def test_authoritative_out_locks_the_projection_to_current_stats():
    result = project_live_player(
        pregame_stats=_smith_prior(),
        live_stats={"receptions": 2, "rec_yards": 30},
        position="WR",
        game_status="live",
        game_progress=0.5,
        ruled_out=True,
    )
    assert result.projection_status == "OUT"
    assert result.projected_remaining_stats["rec_yards"] == 0
    assert _points(result.projected_final_stats) == pytest.approx(5.0)


def test_fantasy_points_only_projection_uses_the_documented_clock_fallback():
    result = project_live_player(
        pregame_stats={}, pregame_fantasy_points=28.9, live_stats={}, position="WR", game_status="live", game_progress=0.25,
    )
    assert result.fallback_reason == "fantasy_points_only"
    assert result.projected_remaining_fantasy_points == pytest.approx(21.675)


def test_same_statline_is_scored_with_each_leagues_rules_at_read_time():
    result = project_live_player(
        pregame_stats=_smith_prior(), live_stats={"targets": 2, "receptions": 1, "rec_yards": 8},
        position="WR", game_status="live", game_progress=0.25,
    )
    full_ppr, _ = calculate_player_fantasy_points(result.projected_final_stats, {"ppr": 1}, "WR")
    half_ppr, _ = calculate_player_fantasy_points(result.projected_final_stats, {"ppr": 0.5}, "WR")
    assert full_ppr - half_ppr == pytest.approx(result.projected_final_stats["receptions"] * 0.5, abs=0.01)


def test_clock_progress_is_regulation_only():
    assert regulation_game_progress(1, "15:00") == 0
    assert regulation_game_progress(2, "15:00") == 0.25
    assert regulation_game_progress(4, "00:00") == 1
    assert regulation_game_progress(None, None) is None
    assert regulation_game_progress(5, "15:00") is None


def test_accepted_snapshot_persists_one_idempotent_model_result(db_session):
    player = Player(name="Jeremiah Smith", school="Ohio State", position="WR")
    game = Game(external_id="espn-smith", season=2026, week=1, home_team="Ohio State", away_team="Ball State")
    db_session.add_all([player, game])
    db_session.flush()
    projection = WeeklyProjection(
        player_id=player.id, season=2026, week=1, fantasy_points=28.9,
        targets=10, receptions=7, rec_yards=99, rec_tds=2,
    )
    snapshot = ProviderGameSnapshot(
        provider="espn", provider_game_id="espn-smith", season=2026, week=1,
        status="live", event_state="live", event_period=2, event_clock="15:00",
        accepted=True, classification="NEWER", snapshot_hash="a" * 64,
        captured_at=datetime.now(timezone.utc), raw_payload={},
        normalized_rows=[{"player_id": player.id, "stats": {"receptions": 0, "rec_yards": 0}}],
    )
    db_session.add_all([projection, snapshot])
    db_session.commit()

    assert persist_live_projections_for_snapshot(db_session, snapshot=snapshot) == 1
    assert persist_live_projections_for_snapshot(db_session, snapshot=snapshot) == 0
    row = db_session.query(LivePlayerProjection).one()
    assert row.model_version == LIVE_PROJECTION_V1
    assert row.projection_status == "LIVE"
    assert row.game_progress == 0.25
