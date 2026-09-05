from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.live_player_projection import LivePlayerProjection
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll
from collegefootballfantasy_api.app.services.espn_live_scoring import _provider_game_ids_for_players
from collegefootballfantasy_api.app.services.espn_stats_sync import persist_normalized_espn_player_stats
from collegefootballfantasy_api.app.services.fantasy_game_selection import fantasy_stat_weeks
from collegefootballfantasy_api.app.services.league_roster_matchup import _final_game_stat_line_map, _final_waiver_score_map, _serialize_team_roster, _live_game_context_by_player
from collegefootballfantasy_api.app.services.player_lock_service import game_context_for_players
from collegefootballfantasy_api.app.services.scoring_service import recalculate_league_week_scores
from tests.api.scoring_helpers import create_scoring_fixture


@pytest.fixture
def opening_slate(db_session):
    league, home, away, players, matchup = create_scoring_fixture(db_session)
    qb = players["qb"]
    qb.school = "USC"
    # Capture the already-earned score before the historical schedule repair.
    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    stat = db_session.query(PlayerStat).filter_by(player_id=qb.id, week=1).one()
    stat.week = 0
    games = []
    for week, day, opponent, status in ((0, 29, "San Jose State", "final"), (1, 4, "Fresno State", "scheduled"), (2, 12, "Next Opponent", "scheduled")):
        game = Game(season=2026, week=week, external_id=f"usc-{week}", home_team="USC",
                    away_team=opponent, schedule_status=status,
                    start_date=datetime(2026, 8 if week == 0 else 9, day, 19, tzinfo=timezone.utc))
        db_session.add(game)
        games.append(game)
    db_session.flush()
    db_session.add(PlayerGameStat(player_id=qb.id, game_id=games[0].id, season=2026, week=0,
                                  source="espn_final_boxscore", stats=dict(stat.stats)))
    db_session.commit()
    return league, home, players, matchup, games


def test_second_game_never_replaces_or_adds_to_earned_week_one_points(db_session, opening_slate):
    league, home, players, matchup, games = opening_slate
    qb = players["qb"]
    score = db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=qb.id, week=1).one()
    earned = (score.fantasy_points, score.source_stat_id, matchup.home_score)
    assert earned[0] == 16.0
    for yards in (0, 50, 600, 600):
        # The real-game feed must still persist tonight's cumulative stats.
        persist_normalized_espn_player_stats(db_session, season=2026, week=1,
            normalized_rows=[{"player_id": qb.id, "stats": {"PassingYards": yards}}])
        db_session.flush()
        recalculate_league_week_scores(db_session, league.id, 2026, 1)
        assert (score.fantasy_points, score.source_stat_id, matchup.home_score) == earned
    assert db_session.query(PlayerStat).filter_by(player_id=qb.id, week=1).one().stats["PassingYards"] == 600
    assert [(game.week, game.away_team) for game in games] == [(0, "San Jose State"), (1, "Fresno State"), (2, "Next Opponent")]
    assert matchup.week == 1


def test_week_two_resumes_normal_scoring_without_changing_week_one(db_session, opening_slate):
    league, home, players, matchup, games = opening_slate
    qb = players["qb"]
    persist_normalized_espn_player_stats(db_session, season=2026, week=2,
        normalized_rows=[{"player_id": qb.id, "stats": {"PassingYards": 300}}])
    db_session.flush()
    recalculate_league_week_scores(db_session, league.id, 2026, 2)
    scores = {row.week: row.fantasy_points for row in db_session.query(PlayerWeekScore).filter_by(player_id=qb.id).all()}
    assert scores == {1: 16.0, 2: 12.0}
    assert matchup.week == 1 and matchup.home_score == 56.0
    starts, opponents, _ = game_context_for_players(db_session, player_ids={qb.id}, season=2026, week=2)
    assert opponents[qb.id] == "Next Opponent"


def test_opening_game_owns_locks_finality_and_league_stat_lines(db_session, opening_slate):
    league, home, players, matchup, games = opening_slate
    qb = players["qb"]
    db_session.add(PlayerGameStat(player_id=qb.id, game_id=games[1].id, season=2026, week=1,
                                  source="espn_final_boxscore", stats={"PassingYards": 600}))
    db_session.flush()
    starts, opponents, _ = game_context_for_players(db_session, player_ids={qb.id}, season=2026, week=1, games=games[:2])
    assert starts[qb.id] == datetime(2026, 8, 29, 19, tzinfo=timezone.utc)
    assert opponents[qb.id] == "San Jose State"
    assert _provider_game_ids_for_players(db_session, player_ids={qb.id}, season=2026, week=1) == {qb.id: "usc-0"}
    lines = _final_game_stat_line_map(db_session, season=2026, week=1, player_ids={qb.id}, player_positions={qb.id: "QB"})
    assert lines[qb.id].startswith("250 PASS YDS")
    scores = _final_waiver_score_map(db_session, season=2026, week=1, player_ids={qb.id},
        player_positions={qb.id: "QB"}, player_schools={qb.id: "USC"}, scoring_rules={"ppr": 1})
    assert scores == {qb.id: 16.0}
    # Both independent game logs remain intact, not summed or overwritten.
    assert db_session.query(PlayerGameStat).filter_by(player_id=qb.id).count() == 2


def test_other_teams_and_unverified_placeholders_do_not_switch_weeks(db_session, opening_slate):
    league, home, players, matchup, games = opening_slate
    ids = {player.id for player in players.values()}
    weeks = fantasy_stat_weeks(db_session, season=2026, week=1, player_ids=ids)
    assert weeks[players["qb"].id] == 0
    assert all(weeks[player.id] == 1 for key, player in players.items() if key != "qb")
    games[0].schedule_status = "scheduled"
    db_session.flush()
    assert set(fantasy_stat_weeks(db_session, season=2026, week=1, player_ids=ids).values()) == {1}


def test_missing_opening_stat_keeps_previous_score_instead_of_using_second_game(db_session, opening_slate):
    league, home, players, matchup, games = opening_slate
    qb = players["qb"]
    # The old source row can be unavailable during an import. Never substitute
    # the excluded game, even if it has a complete, high-scoring box score.
    db_session.query(PlayerStat).filter_by(player_id=qb.id, week=0).one().week = 3
    persist_normalized_espn_player_stats(db_session, season=2026, week=1,
        normalized_rows=[{"player_id": qb.id, "stats": {"PassingYards": 600}}])
    db_session.flush()
    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    score = db_session.query(PlayerWeekScore).filter_by(player_id=qb.id, week=1).one()
    assert score.fantasy_points == 16.0
    assert score.status == "stale"
    assert matchup.home_score == 56.0


def test_live_second_game_cannot_leak_into_roster_points_or_remaining_projection(db_session, opening_slate):
    league, home, players, matchup, games = opening_slate
    qb = players["qb"]
    now = datetime(2026, 9, 5, 2, tzinfo=timezone.utc)
    db_session.add(LivePlayerProjection(player_id=qb.id, game_id=games[1].id, season=2026, week=1,
        provider="espn", provider_snapshot_hash="second-game", provider_snapshot_at=now,
        model_version="test", projection_status="LIVE", current_stats_json={"pass_yards": 600},
        projected_final_stats_json={"pass_yards": 800}, projected_remaining_fantasy_points=40,
        input_hash="second-game", calculated_at=now))
    for week, state in ((0, "post"), (1, "in")):
        db_session.add(ProviderGamePoll(provider="espn", provider_game_id=f"usc-{week}", season=2026,
            week=week, status="final" if week == 0 else "live", accepted_snapshot_hash=f"hash-{week}",
            latest_payload={"header": {"competitions": [{"status": {"type": {"state": state}}}]}}))
    db_session.flush()
    context = _live_game_context_by_player(db_session, season=2026, week=1, player_schools={qb.id: "USC"})
    assert context[qb.id].state == "final"
    row = next(row for row in _serialize_team_roster(db_session, league, home, 1) if row.player_id == qb.id)
    assert row.current_fantasy_points == 16.0
    assert row.live_projected_final_points is None
    assert row.live_game_state == "final"
    assert row.is_locked is True
    assert row.opponent == "San Jose State"
