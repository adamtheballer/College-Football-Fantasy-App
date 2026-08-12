"""Controlled Week 9, 2025 ESPN replay for the shadow live-scoring pipeline.

The final stat totals below are the official structured ESPN box-score values
for Texas A&M at LSU (event ``401752748``, October 25, 2025).  ESPN's public
historical endpoint retains the final box score, not the intermediate
three-minute snapshots.  The first payload is therefore explicitly a
controlled partial replay used only to test live-to-final transitions; it is
not presented as a historical halftime box score.

This test uses the disposable test database and never instantiates the ESPN
HTTP adapter.  It is a regression test for the production *shadow* pipeline,
not an import or a change to the live beta database.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.live_scoring_contract import FINAL_UNVERIFIED, IN_PROGRESS
from collegefootballfantasy_api.app.integrations.espn_live_scoring_adapter import (
    EspnAthleteStatLine,
    EspnGame,
    EspnGameSummary,
    EspnLiveScoringAdapter,
)
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.live_scoring import (
    PlayerGameStatRevision,
    ProviderGameIdentity,
    ProviderGamePollState,
    ProviderRawEvent,
    ScoringCalculationSnapshot,
    ShadowScoringReadModel,
)
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.services.live_scoring_service import (
    ensure_relevant_espn_poll_states,
    ingest_espn_game_summary,
    process_one_scoring_work_item,
)
from tests.api.scoring_helpers import create_scoring_fixture


EVENT_ID = "401752748"
SEASON = 2025
WEEK = 9
KICKOFF = datetime(2025, 10, 25, 23, 30, tzinfo=timezone.utc)


def _week9_summary(*, stage: str, status: str, marcel_pass_yards: int, include_all_players: bool) -> EspnGameSummary:
    """Create one stored provider response without performing provider I/O."""
    lines = [
        EspnAthleteStatLine(
            athlete_id="4870971",
            athlete_name="Marcel Reed",
            team_id="245",
            stats={
                "pass_completions": 6 if status == IN_PROGRESS else 12,
                "pass_attempts": 10 if status == IN_PROGRESS else 21,
                "pass_yards": marcel_pass_yards,
                "pass_tds": 1 if status == IN_PROGRESS else 2,
                "interceptions": 1 if status == IN_PROGRESS else 2,
                "rush_attempts": 7 if status == IN_PROGRESS else 13,
                "rush_yards": 54 if status == IN_PROGRESS else 108,
                "rush_tds": 1 if status == IN_PROGRESS else 2,
            },
            completeness="complete",
        )
    ]
    if include_all_players:
        lines.extend(
            [
                EspnAthleteStatLine(
                    athlete_id="5122231",
                    athlete_name="Harlem Berry",
                    team_id="99",
                    stats={
                        "rush_attempts": 5 if status == IN_PROGRESS else 9,
                        "rush_yards": 30 if status == IN_PROGRESS else 59,
                        "rush_tds": 1,
                    },
                    completeness="complete",
                ),
                EspnAthleteStatLine(
                    athlete_id="4870653",
                    athlete_name="KC Concepcion",
                    team_id="245",
                    stats={
                        "receptions": 2 if status == IN_PROGRESS else 3,
                        "rec_yards": 30 if status == IN_PROGRESS else 45,
                        "rec_tds": 1,
                    },
                    completeness="complete",
                ),
                EspnAthleteStatLine(
                    athlete_id="5079420",
                    athlete_name="Trey'Dez Green",
                    team_id="99",
                    stats={
                        "receptions": 3 if status == IN_PROGRESS else 6,
                        "rec_yards": 27 if status == IN_PROGRESS else 54,
                        "rec_tds": 1,
                    },
                    completeness="complete",
                ),
                # ESPN's adapter emits normalized numeric kicking totals. Its
                # summary lacks the field-goal distance tiers required by our
                # kicker contract, so this line must remain blocked rather
                # than creating a guessed kicker score.
                EspnAthleteStatLine(
                    athlete_id="4879612",
                    athlete_name="Randy Bond",
                    team_id="245",
                    stats={"xp_made": 3 if status == IN_PROGRESS else 7, "fg_missed": 0},
                    completeness="incomplete",
                ),
            ]
        )
    payload = {
        "source": "espn_week_9_2025_final_box_score",
        "event_id": EVENT_ID,
        "replay_stage": stage,
        "status": status,
        "marcel_pass_yards": marcel_pass_yards,
        "source_is_network_fetch": False,
    }
    return EspnGameSummary(
        game=EspnGame(
            game_id=EVENT_ID,
            status=status,
            season=SEASON,
            week=WEEK,
            start_at=KICKOFF,
            payload=payload,
        ),
        athlete_lines=tuple(lines),
        payload=payload,
    )


def _process_all_scoring_work(db_session) -> int:
    processed = 0
    while True:
        item = process_one_scoring_work_item(db_session, worker_id="week-9-replay")
        if item is None:
            return processed
        processed += 1
        assert processed < 30, "the bounded replay must not create an unbounded work loop"


def _snapshot_score(db_session, *, player_id: int, revision_number: int) -> float:
    snapshot = (
        db_session.query(ScoringCalculationSnapshot)
        .join(PlayerGameStatRevision, PlayerGameStatRevision.id == ScoringCalculationSnapshot.stat_revision_id)
        .filter(
            ScoringCalculationSnapshot.player_id == player_id,
            PlayerGameStatRevision.revision_number == revision_number,
        )
        .one()
    )
    return snapshot.score


def test_week_9_2025_espn_replay_stays_shadow_only_and_handles_a_final_correction(client, db_session, monkeypatch):
    """Replay QB/RB/WR/TE finals plus one safely blocked kicker line.

    The exact final scores use the league's standard PPR fixture rules:
    Marcel Reed 34.88, Harlem Berry 11.90, KC Concepcion 13.50, and
    Trey'Dez Green 17.40.  A controlled one-yard correction to Reed proves
    that a subsequent provider payload appends immutable evidence instead of
    overwriting the final snapshot.
    """
    # This replay is fully local.  If a future refactor tries to turn it into
    # an ESPN request, fail the test immediately.
    monkeypatch.setattr(
        EspnLiveScoringAdapter,
        "fetch_game_summary",
        lambda *_args, **_kwargs: pytest.fail("the historical replay must not call ESPN"),
    )
    monkeypatch.setattr(settings, "scoring_mode", "shadow")

    league, _home, _away, players, matchup = create_scoring_fixture(db_session)
    league.season_year = SEASON
    authoritative_players = {
        "qb": ("Marcel Reed", "QB", "Texas A&M Aggies", "4870971"),
        "rb": ("Harlem Berry", "RB", "LSU Tigers", "5122231"),
        "wr": ("KC Concepcion", "WR", "Texas A&M Aggies", "4870653"),
        "bench": ("Trey'Dez Green", "TE", "LSU Tigers", "5079420"),
    }
    for key, (name, position, school, provider_id) in authoritative_players.items():
        player = players[key]
        player.name, player.position, player.school, player.cfb27_rank = name, position, school, 1
        db_session.add(
            PlayerProviderId(
                player_id=player.id,
                provider="espn",
                provider_player_id=provider_id,
                verification_status="verified",
            )
        )

    kicker = Player(name="Randy Bond", position="K", school="Texas A&M Aggies", cfb27_rank=100)
    db_session.add(kicker)
    db_session.flush()
    db_session.add(
        PlayerProviderId(
            player_id=kicker.id,
            provider="espn",
            provider_player_id="4879612",
            verification_status="verified",
        )
    )
    game = Game(
        external_id=EVENT_ID,
        season=SEASON,
        week=WEEK,
        season_type="regular",
        start_date=KICKOFF,
        home_team="LSU Tigers",
        away_team="Texas A&M Aggies",
    )
    db_session.add(game)
    db_session.flush()
    db_session.add(
        ProviderGameIdentity(
            provider="espn",
            provider_game_id=EVENT_ID,
            game_id=game.id,
            verification_status="verified",
            source_metadata={"source": "ESPN", "replay": "week_9_2025"},
        )
    )
    db_session.commit()

    public_stat_count = db_session.query(PlayerStat).count()
    original_matchup_status = matchup.status
    assert ensure_relevant_espn_poll_states(db_session, season=SEASON, week=WEEK) == 1
    state = db_session.query(ProviderGamePollState).one()

    partial = ingest_espn_game_summary(
        db_session,
        state_id=state.id,
        summary=_week9_summary(
            stage="controlled_partial_replay",
            status=IN_PROGRESS,
            marcel_pass_yards=101,
            include_all_players=True,
        ),
    )
    assert partial["revisions"] == 5
    assert partial["identity_unmatched"] == 0
    assert partial["final_certified"] == 0
    assert _process_all_scoring_work(db_session) == 8

    final = ingest_espn_game_summary(
        db_session,
        state_id=state.id,
        summary=_week9_summary(
            stage="official_final_box_score",
            status=FINAL_UNVERIFIED,
            marcel_pass_yards=202,
            include_all_players=True,
        ),
    )
    assert final["revisions"] == 5
    assert final["identity_unmatched"] == 0
    assert _process_all_scoring_work(db_session) == 8

    correction = ingest_espn_game_summary(
        db_session,
        state_id=state.id,
        summary=_week9_summary(
            stage="controlled_final_correction",
            status=FINAL_UNVERIFIED,
            marcel_pass_yards=203,
            include_all_players=False,
        ),
    )
    assert correction["revisions"] == 1
    assert _process_all_scoring_work(db_session) == 2

    assert _snapshot_score(db_session, player_id=players["qb"].id, revision_number=2) == pytest.approx(34.88)
    assert _snapshot_score(db_session, player_id=players["rb"].id, revision_number=2) == pytest.approx(11.90)
    assert _snapshot_score(db_session, player_id=players["wr"].id, revision_number=2) == pytest.approx(13.50)
    assert _snapshot_score(db_session, player_id=players["bench"].id, revision_number=2) == pytest.approx(17.40)
    assert _snapshot_score(db_session, player_id=players["qb"].id, revision_number=3) == pytest.approx(34.92)

    kicker_revision = (
        db_session.query(PlayerGameStatRevision)
        .filter(PlayerGameStatRevision.player_id == kicker.id)
        .order_by(PlayerGameStatRevision.revision_number.desc())
        .first()
    )
    assert kicker_revision is not None
    assert kicker_revision.status == "blocked_incomplete"
    assert db_session.query(ScoringCalculationSnapshot).filter_by(player_id=kicker.id).count() == 0

    # The public beta score sources remain exactly as they were.  The replay
    # adds only append-only provider evidence and immutable shadow snapshots.
    # The per-league shadow read model is intentionally refreshed in place so
    # consumers have one current, non-public projection to read.
    assert db_session.query(PlayerStat).count() == public_stat_count
    assert matchup.status == original_matchup_status
    assert db_session.query(ProviderRawEvent).count() == 3
    assert db_session.query(PlayerGameStatRevision).count() == 11
    assert db_session.query(ScoringCalculationSnapshot).count() == 9
    assert db_session.query(ScoringCalculationSnapshot).filter_by(publish_state="shadow").count() == 9
    assert db_session.query(ShadowScoringReadModel).count() == 1
