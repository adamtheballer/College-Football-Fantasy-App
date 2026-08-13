"""Tests for the read-only public-finalization preview boundary."""

from __future__ import annotations

from datetime import datetime, timezone

from collegefootballfantasy_api.app.domain.live_scoring_contract import COMPLETE, FINAL_VERIFIED
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.live_scoring import (
    PlayerGameStatRevision,
    ProviderGamePollState,
    ProviderRawEvent,
)
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.services.live_scoring_promotion_preview import (
    build_final_scoring_promotion_preview,
)


def test_finalization_preview_refuses_an_empty_week(db_session):
    preview = build_final_scoring_promotion_preview(db_session, season=2025, week=9)

    assert preview.status == "blocked"
    assert preview.database_writes == 0
    assert preview.player_stat_plans == ()
    assert preview.blockers == ({"kind": "NO_FINAL_STAT_REVISIONS", "season": 2025, "week": 9},)


def test_finalization_preview_is_read_only_and_becomes_ready_only_with_certified_complete_evidence(db_session):
    now = datetime(2025, 10, 25, 23, 30, tzinfo=timezone.utc)
    player = Player(name="Replay Back", position="RB", school="Replay University", cfb27_rank=1)
    game = Game(
        external_id="replay-game-1",
        season=2025,
        week=9,
        season_type="regular",
        start_date=now,
        home_team="Replay University",
        away_team="Opponent University",
    )
    db_session.add_all((player, game))
    db_session.flush()
    raw_event = ProviderRawEvent(
        provider="espn",
        feed="live_boxscore",
        endpoint_type="game_summary",
        provider_event_id="replay-final-1",
        request_key="replay-final-1",
        event_type="game_boxscore",
        season=2025,
        week=9,
        provider_game_id="replay-game-1",
        payload_json={"replay": True},
        payload_sha256="a" * 64,
        received_at=now,
        processing_status="processed",
    )
    db_session.add(raw_event)
    db_session.flush()
    revision = PlayerGameStatRevision(
        raw_event_id=raw_event.id,
        player_id=player.id,
        game_id=game.id,
        provider="espn",
        provider_player_id="replay-player-1",
        provider_game_id="replay-game-1",
        season=2025,
        week=9,
        revision_number=1,
        lifecycle_state=FINAL_VERIFIED,
        completeness=COMPLETE,
        status="accepted",
        stats_json={"rush_yards": 100.0, "rush_tds": 1.0},
        missing_keys_json=[],
        source_hash="b" * 64,
        created_at=now,
    )
    state = ProviderGamePollState(
        provider="espn",
        provider_game_id="replay-game-1",
        game_id=game.id,
        season=2025,
        week=9,
        lifecycle_state=FINAL_VERIFIED,
        final_fetch_stage="next_day",
        operator_status="final_verified",
    )
    db_session.add_all((revision, state))
    db_session.flush()

    before = (db_session.query(PlayerStat).count(), db_session.query(PlayerGameStat).count())
    preview = build_final_scoring_promotion_preview(db_session, season=2025, week=9)
    assert preview.status == "ready_for_authorized_promotion"
    assert preview.database_writes == 0
    assert preview.blockers == ()
    assert len(preview.player_stat_plans) == 1
    plan = preview.player_stat_plans[0]
    assert plan.player_stat_action == "CREATE"
    assert plan.player_game_stat_action == "CREATE"
    assert plan.fantasy_points > 0
    assert set(preview.dependent_recalculations.values()) == {"requires_authorized_public_promotion"}
    assert (db_session.query(PlayerStat).count(), db_session.query(PlayerGameStat).count()) == before

    final_stats = {**revision.stats_json, "fantasy_points": plan.fantasy_points}
    db_session.add_all((
        PlayerStat(
            player_id=player.id,
            season=2025,
            week=9,
            source="espn_live_final_v1",
            verified=True,
            stats=final_stats,
        ),
        PlayerGameStat(
            player_id=player.id,
            game_id=game.id,
            season=2025,
            week=9,
            source="espn_live_final_v1",
            stats=final_stats,
        ),
    ))
    db_session.flush()
    after_existing = build_final_scoring_promotion_preview(db_session, season=2025, week=9)
    assert after_existing.player_stat_plans[0].player_stat_action == "UNCHANGED"
    assert after_existing.player_stat_plans[0].player_game_stat_action == "UNCHANGED"
