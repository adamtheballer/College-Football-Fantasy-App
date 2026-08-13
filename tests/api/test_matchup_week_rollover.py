from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.services.league_weeks import resolve_current_week
from collegefootballfantasy_api.app.services.league_workspace import build_standings_summary
from collegefootballfantasy_api.app.services.scoring_service import recalculate_standings_for_week


UTC = timezone.utc


def _league_with_two_weeks(db_session):
    league = League(name="Rollover League", season_year=2026, max_teams=4, status="post_draft")
    db_session.add(league)
    db_session.flush()
    teams = [Team(league_id=league.id, name=f"Team {index}") for index in range(1, 5)]
    db_session.add_all(teams)
    db_session.flush()
    week_one = Matchup(
        league_id=league.id,
        season=2026,
        week=1,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        status="final",
        home_score=120.0,
        away_score=110.0,
    )
    week_two = Matchup(
        league_id=league.id,
        season=2026,
        week=2,
        home_team_id=teams[2].id,
        away_team_id=teams[3].id,
        status="projected",
        home_score=0.0,
        away_score=0.0,
    )
    db_session.add_all([week_one, week_two])
    db_session.flush()
    return league, teams, week_one, week_two


def test_final_matchup_stays_visible_until_tuesday_after_full_results_window(db_session):
    league, _teams, week_one, _week_two = _league_with_two_weeks(db_session)
    # Monday 11 PM Eastern: this was the final game of the matchup week.
    week_one.updated_at = datetime(2026, 8, 25, 3, 0, tzinfo=UTC)
    db_session.commit()

    # A full 24 hours has not elapsed, so Week 1 remains the default even on Tuesday.
    assert resolve_current_week(db_session, league, now=datetime(2026, 8, 25, 16, 0, tzinfo=UTC)) == 1
    # Once the final-result hold has elapsed, the next projected matchup is shown.
    assert resolve_current_week(db_session, league, now=datetime(2026, 8, 26, 4, 0, tzinfo=UTC)) == 2


def test_rollover_waits_for_every_league_matchup_to_finish(db_session):
    league, teams, week_one, _week_two = _league_with_two_weeks(db_session)
    db_session.add(
        Matchup(
            league_id=league.id,
            season=2026,
            week=1,
            home_team_id=teams[2].id,
            away_team_id=teams[3].id,
            status="live",
            home_score=42.0,
            away_score=40.0,
        )
    )
    week_one.updated_at = datetime(2026, 8, 23, 2, 0, tzinfo=UTC)
    db_session.commit()

    assert resolve_current_week(db_session, league, now=datetime(2026, 8, 26, 16, 0, tzinfo=UTC)) == 1


def test_late_tuesday_correction_only_holds_results_for_one_day(db_session):
    league, _teams, week_one, _week_two = _league_with_two_weeks(db_session)
    week_one.updated_at = datetime(2026, 8, 25, 23, 0, tzinfo=UTC)
    db_session.commit()

    assert resolve_current_week(db_session, league, now=datetime(2026, 8, 26, 22, 0, tzinfo=UTC)) == 1
    assert resolve_current_week(db_session, league, now=datetime(2026, 8, 27, 0, 0, tzinfo=UTC)) == 2


def test_standings_only_publish_after_the_whole_week_is_final(db_session):
    league, teams, week_one, week_two = _league_with_two_weeks(db_session)
    db_session.add(
        Matchup(
            league_id=league.id,
            season=2026,
            week=1,
            home_team_id=teams[2].id,
            away_team_id=teams[3].id,
            status="final",
            home_score=90.0,
            away_score=80.0,
        )
    )
    db_session.flush()

    # Week 2 is projected, so the standings snapshot is safe to publish at Week 1 only.
    assert recalculate_standings_for_week(db_session, league.id, 2026, 2) == 4
    assert db_session.query(Standing).filter_by(league_id=league.id, week=1).count() == 4
    assert db_session.query(Standing).filter_by(league_id=league.id, week=2).count() == 0

    # A stale partial snapshot cannot leak into the user-facing standings.
    db_session.add(
        Standing(
            league_id=league.id,
            team_id=teams[0].id,
            season=2026,
            week=2,
            wins=99,
            losses=0,
            ties=0,
            points_for=999.0,
            points_against=0.0,
        )
    )
    db_session.commit()
    rows = build_standings_summary(db_session, league)
    assert rows[0].wins == 1
    assert rows[0].points_for == 120.0
    assert week_two.status == "projected"
