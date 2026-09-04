from datetime import datetime, timedelta, timezone

from sqlalchemy import event

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.live_player_projection import LivePlayerProjection
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.league_roster_matchup import (
    _starter_live_totals,
    _starter_projection_total,
    build_matchup_tab_view,
)
from collegefootballfantasy_api.app.services.scoring_service import recalculate_league_week_scores
from tests.api.scoring_helpers import create_scoring_fixture


def test_missing_or_bye_starters_reduce_matchup_inputs_without_hiding_probability():
    class Starter:
        is_starter = True
        status = "STARTER"
        projection_status = "BYE"
        projected_points = None
        pregame_projected_points = None
        live_game_state = None
        current_fantasy_points = None
        live_projected_final_points = None

    assert _starter_projection_total([Starter()]) == 0.0
    assert _starter_live_totals([Starter()]) == (0.0, 0.0, 0.0, False)


def test_matchup_tab_uses_a_bounded_number_of_selects(client, db_session):
    league, home, away, _players, _matchup = create_scoring_fixture(db_session)
    user = User(
        first_name="Performance",
        email="performance@example.com",
        password_hash="hash",
        api_token="performance-token",
    )
    db_session.add(user)
    db_session.flush()
    home.owner_user_id = user.id
    db_session.add_all(
        [
            Standing(league_id=league.id, team_id=home.id, season=2026, week=1, wins=1, losses=0, ties=0),
            Standing(league_id=league.id, team_id=away.id, season=2026, week=1, wins=0, losses=1, ties=0),
        ]
    )
    db_session.commit()
    db_session.expire_all()
    db_session.refresh(league)
    db_session.refresh(user)

    select_count = 0

    def count_selects(_connection, _cursor, statement, _parameters, _context, _executemany):
        nonlocal select_count
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    event.listen(db_session.bind, "before_cursor_execute", count_selects)
    try:
        response = build_matchup_tab_view(db_session, league, user, selected_week=1)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", count_selects)

    assert response.my_team is not None
    assert response.opponent_team is not None
    assert response.my_team.manager_name == home.owner_name
    assert response.opponent_team.manager_name == away.owner_name
    assert len(response.my_roster) == 8
    assert len(response.opponent_roster) == 8
    # Player-level live scoring, verified final box-score stat lines, official
    # availability, and the server-authoritative permanent-rival lookup are
    # each one bounded query, never one query per roster slot.
    # Keep this cap tight so the matchup view cannot regress into an N+1 read.
    assert select_count <= 13


def test_matchup_tab_marks_the_week_started_after_a_verified_kickoff(client, db_session):
    league, home, _away, _players, _matchup = create_scoring_fixture(db_session)
    user = User(
        first_name="Week start",
        email="week-start@example.com",
        password_hash="hash",
        api_token="week-start-token",
    )
    db_session.add(user)
    db_session.flush()
    home.owner_user_id = user.id
    db_session.add(
        TeamSchedule(
            team_name="Test",
            season=2026,
            week=1,
            location="home",
            is_bye=False,
            kickoff_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db_session.commit()

    response = build_matchup_tab_view(db_session, league, user, selected_week=1)

    assert response.week_started is True


def test_matchup_transitions_to_live_at_kickoff_before_provider_play_data_arrives(client, db_session):
    league, home, _away, players, _matchup = create_scoring_fixture(db_session)
    user = User(
        first_name="Kickoff",
        email="kickoff-transition@example.com",
        password_hash="hash",
        api_token="kickoff-transition-token",
    )
    db_session.add(user)
    db_session.flush()
    home.owner_user_id = user.id
    db_session.add(
        Game(
            season=2026,
            week=1,
            schedule_status="scheduled",
            start_date=datetime.now(timezone.utc) - timedelta(seconds=1),
            home_team="Test",
            away_team="Rival",
        )
    )
    db_session.commit()

    response = build_matchup_tab_view(db_session, league, user, selected_week=1)
    quarterback = next(row for row in response.my_roster if row.player_id == players["qb"].id)

    assert quarterback.live_game_state == "live"
    assert quarterback.current_fantasy_points is None
    assert response.status == "live"


def test_matchup_tab_exposes_persisted_player_scores_without_falling_back_to_projections(client, db_session):
    league, home, _away, players, _matchup = create_scoring_fixture(db_session)
    user = User(
        first_name="Live",
        email="live-matchup@example.com",
        password_hash="hash",
        api_token="live-matchup-token",
    )
    db_session.add(user)
    db_session.flush()
    home.owner_user_id = user.id
    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    response = build_matchup_tab_view(db_session, league, user, selected_week=1)
    quarterback = next(row for row in response.my_roster if row.player_id == players["qb"].id)
    open_slot = next(row for row in response.my_roster if row.status == "EMPTY")

    assert quarterback.live_points == 16.0
    assert quarterback.live_scoring_status == "live"
    assert quarterback.live_scoring_updated_at is not None
    assert open_slot.live_points is None
    assert open_slot.live_scoring_status == "unavailable"


def test_matchup_tab_exposes_current_stat_lines_for_live_starter_and_bench_rows(client, db_session):
    league, home, _away, players, _matchup = create_scoring_fixture(db_session)
    user = User(
        first_name="Live lines",
        email="live-lines-matchup@example.com",
        password_hash="hash",
        api_token="live-lines-token",
    )
    db_session.add(user)
    db_session.flush()
    home.owner_user_id = user.id
    game = Game(
        season=2026,
        week=1,
        schedule_status="in_progress",
        start_date=datetime.now(timezone.utc) - timedelta(minutes=1),
        home_team="Test",
        away_team="Rival",
    )
    db_session.add(game)
    db_session.flush()
    snapshot_at = datetime.now(timezone.utc)
    db_session.add_all([
        LivePlayerProjection(
            player_id=players["qb"].id,
            game_id=game.id,
            season=2026,
            week=1,
            provider="espn",
            provider_snapshot_hash="live-qb-line-prior",
            provider_snapshot_at=snapshot_at - timedelta(minutes=3),
            model_version="live_projection_v1",
            projection_status="LIVE",
            current_stats_json={"pass_yards": 90, "pass_tds": 1, "rush_yards": 8, "rush_tds": 0},
            projected_final_stats_json={},
            projected_remaining_stats_json={},
            observability_json={},
            input_hash="live-qb-line-prior",
            calculated_at=snapshot_at - timedelta(minutes=3),
        ),
        LivePlayerProjection(
            player_id=players["qb"].id,
            game_id=game.id,
            season=2026,
            week=1,
            provider="espn",
            provider_snapshot_hash="live-qb-line",
            provider_snapshot_at=snapshot_at,
            model_version="live_projection_v1",
            projection_status="LIVE",
            current_stats_json={"pass_yards": 184, "pass_tds": 2, "rush_yards": 21, "rush_tds": 1},
            projected_final_stats_json={},
            projected_remaining_stats_json={},
            observability_json={},
            input_hash="live-qb-line",
            calculated_at=snapshot_at,
        ),
        LivePlayerProjection(
            player_id=players["bench"].id,
            game_id=game.id,
            season=2026,
            week=1,
            provider="espn",
            provider_snapshot_hash="live-bench-line",
            provider_snapshot_at=snapshot_at,
            model_version="live_projection_v1",
            projection_status="LIVE",
            current_stats_json={"receptions": 4, "rec_yards": 67, "rec_tds": 1},
            projected_final_stats_json={},
            projected_remaining_stats_json={},
            observability_json={},
            input_hash="live-bench-line",
            calculated_at=snapshot_at,
        ),
    ])
    db_session.commit()

    response = build_matchup_tab_view(db_session, league, user, selected_week=1)
    roster_by_player = {row.player_id: row for row in response.my_roster if row.player_id}

    assert roster_by_player[players["qb"].id].live_game_state == "live"
    assert roster_by_player[players["qb"].id].game_stat_line == "184 PASS YDS · 2 PASS TD · 21 RUSH YDS · 1 RUSH TD"
    assert roster_by_player[players["bench"].id].live_game_state == "live"
    assert roster_by_player[players["bench"].id].game_stat_line == "4 REC · 67 REC YDS · 1 REC TD"


def test_matchup_tab_exposes_verified_final_stat_line_for_a_completed_roster_game(client, db_session):
    league, home, _away, players, _matchup = create_scoring_fixture(db_session)
    user = User(
        first_name="Final line",
        email="final-line-matchup@example.com",
        password_hash="hash",
        api_token="final-line-token",
    )
    db_session.add(user)
    db_session.flush()
    home.owner_user_id = user.id
    game = Game(season=2026, week=1, home_team="Test", away_team="Rival", home_points=31, away_points=24)
    db_session.add(game)
    db_session.flush()
    db_session.add(
        PlayerGameStat(
            player_id=players["qb"].id,
            game_id=game.id,
            season=2026,
            week=1,
            source="espn_final_boxscore",
            stats={"pass_yards": 281, "pass_tds": 3, "rush_yards": 34, "rush_tds": 1},
        )
    )
    db_session.commit()

    response = build_matchup_tab_view(db_session, league, user, selected_week=1)
    quarterback = next(row for row in response.my_roster if row.player_id == players["qb"].id)

    assert quarterback.live_game_state == "final"
    assert quarterback.game_stat_line == "281 PASS YDS · 3 PASS TD · 34 RUSH YDS · 1 RUSH TD"
    assert quarterback.final_game_stat_line == "281 PASS YDS · 3 PASS TD · 34 RUSH YDS · 1 RUSH TD"
