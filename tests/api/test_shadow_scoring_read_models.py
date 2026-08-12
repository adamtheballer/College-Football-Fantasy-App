from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.live_scoring import ShadowScoringReadModel
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.services.live_scoring_read_model_service import (
    ShadowReadModelError,
    build_shadow_read_model,
    latest_shadow_read_model,
    persist_shadow_read_model,
)
from collegefootballfantasy_api.app.services.live_scoring_service import (
    ProviderEventInput,
    calculate_snapshot,
    record_provider_event,
    record_stat_revision,
)
from tests.api.test_live_scoring_hardening import _identity_ready_fixture


def _final_score(db_session, league, *, event_id: str, yards: int, lifecycle_state: str = "final"):
    event = record_provider_event(
        db_session,
        ProviderEventInput(
            provider="trusted",
            feed="live_box_score",
            provider_event_id=event_id,
            provider_player_id="provider-qb-1",
            provider_game_id="provider-game-1",
            season=2026,
            week=1,
            payload={"event": event_id, "stats": {"PassingYards": yards}},
        ),
    )
    revision = record_stat_revision(
        db_session,
        raw_event=event,
        position="QB",
        season=2026,
        week=1,
        lifecycle_state=lifecycle_state,
        completeness="complete",
        stats={"PassingYards": yards},
    )
    return calculate_snapshot(db_session, league_id=league.id, revision=revision, scoring_rules={})


def test_shadow_read_model_is_deterministic_and_never_writes_legacy_scores(client, db_session, monkeypatch):
    league, player, _game = _identity_ready_fixture(db_session)
    # The scoring helper has created the teams but not immutable lineup locks.
    # Find the roster owner directly through the existing matchup fixture.
    from collegefootballfantasy_api.app.models.roster import RosterEntry

    home_team_id = db_session.query(RosterEntry.team_id).filter(RosterEntry.player_id == player.id).scalar()
    db_session.add(
        LineupWeekSnapshot(
            league_id=league.id,
            team_id=home_team_id,
            player_id=player.id,
            season=2026,
            week=1,
            slot="QB",
            is_starter=True,
            game_start_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
            locked_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
        )
    )
    db_session.commit()
    monkeypatch.setattr(settings, "scoring_mode", "shadow")

    before = {
        "player_week_scores": db_session.query(PlayerWeekScore).count(),
        "team_week_scores": db_session.query(TeamWeekScore).count(),
        "standings": db_session.query(Standing).count(),
        "shadow_models": db_session.query(ShadowScoringReadModel).count(),
        "matchup_scores": [
            (matchup.id, matchup.status, matchup.home_score, matchup.away_score)
            for matchup in db_session.query(Matchup).filter(Matchup.league_id == league.id).all()
        ],
    }
    first_snapshot = _final_score(db_session, league, event_id="event-shadow-1", yards=250)

    first = build_shadow_read_model(db_session, league_id=league.id, season=2026, week=1)
    again = build_shadow_read_model(db_session, league_id=league.id, season=2026, week=1)
    assert first.source_sha256 == again.source_sha256
    assert first.status == "unavailable"  # Opposing locked lineup evidence is intentionally absent.
    home = next(team for team in first.payload["teams"] if team["team_id"] == home_team_id)
    assert home["starter_points"] == first_snapshot.score == 10.0
    assert home["lineup"][0]["score"] == 10.0
    assert db_session.query(ShadowScoringReadModel).count() == before["shadow_models"]
    assert db_session.query(PlayerWeekScore).count() == before["player_week_scores"]
    assert db_session.query(TeamWeekScore).count() == before["team_week_scores"]
    assert db_session.query(Standing).count() == before["standings"]
    assert [
        (matchup.id, matchup.status, matchup.home_score, matchup.away_score)
        for matchup in db_session.query(Matchup).filter(Matchup.league_id == league.id).all()
    ] == before["matchup_scores"]

    saved = persist_shadow_read_model(db_session, first)
    duplicate = persist_shadow_read_model(db_session, again)
    assert duplicate.id == saved.id
    assert latest_shadow_read_model(db_session, league_id=league.id, season=2026, week=1).id == saved.id
    assert db_session.query(ShadowScoringReadModel).count() == before["shadow_models"] + 1
    assert db_session.query(PlayerWeekScore).count() == before["player_week_scores"]
    assert db_session.query(TeamWeekScore).count() == before["team_week_scores"]
    assert db_session.query(Standing).count() == before["standings"]
    assert [
        (matchup.id, matchup.status, matchup.home_score, matchup.away_score)
        for matchup in db_session.query(Matchup).filter(Matchup.league_id == league.id).all()
    ] == before["matchup_scores"]


def test_shadow_read_model_uses_corrected_revision_and_requires_shadow_mode(client, db_session, monkeypatch):
    league, player, _game = _identity_ready_fixture(db_session)
    from collegefootballfantasy_api.app.models.roster import RosterEntry

    home_team_id = db_session.query(RosterEntry.team_id).filter(RosterEntry.player_id == player.id).scalar()
    db_session.add(
        LineupWeekSnapshot(
            league_id=league.id,
            team_id=home_team_id,
            player_id=player.id,
            season=2026,
            week=1,
            slot="QB",
            is_starter=True,
        )
    )
    db_session.commit()
    monkeypatch.setattr(settings, "scoring_mode", "shadow")
    _final_score(db_session, league, event_id="event-shadow-first", yards=250)
    original = build_shadow_read_model(db_session, league_id=league.id, season=2026, week=1)
    _final_score(db_session, league, event_id="event-shadow-correction", yards=300, lifecycle_state="corrected")
    corrected = build_shadow_read_model(db_session, league_id=league.id, season=2026, week=1)

    home = next(team for team in corrected.payload["teams"] if team["team_id"] == home_team_id)
    assert corrected.source_sha256 != original.source_sha256
    assert home["starter_points"] == 12.0
    assert home["lineup"][0]["revision_number"] == 2

    monkeypatch.setattr(settings, "scoring_mode", "disabled")
    with pytest.raises(ShadowReadModelError, match="SCORING_MODE=shadow"):
        persist_shadow_read_model(db_session, corrected)
