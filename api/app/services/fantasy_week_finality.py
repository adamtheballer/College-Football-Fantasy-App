"""Shared authority for when a fantasy week is safe to publish as complete."""
from __future__ import annotations

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.matchup import Matchup


FINAL_MATCHUP_STATUSES = frozenset({"final", "stat_corrected"})
MAX_REGULAR_SEASON_WEEK = 13


def published_finalized_weeks(db: Session, *, season: int) -> set[int]:
    """Retain weeks that were certified before later administrative changes."""
    from collegefootballfantasy_api.app.models.player_chart_week import PlayerChartPublicationRun
    return {week for (week,) in db.query(PlayerChartPublicationRun.week).filter(PlayerChartPublicationRun.season==season,PlayerChartPublicationRun.status.in_(("complete","partial")),PlayerChartPublicationRun.coverage_json["metric"].as_string()=="actual").distinct().all()}


def latest_known_finalized_week(db: Session, *, season: int) -> int:
    # Historical input safety is different from the uninterrupted calendar
    # cursor: a later certified week proves that old current inputs are late.
    return max(published_finalized_weeks(db,season=season) | {w for w in range(1,14) if week_is_authoritatively_finalized(db,season=season,week=w)},default=0)


def week_is_authoritatively_finalized(db: Session, *, season: int, week: int) -> bool:
    """Return true only when every persisted app matchup for a week is final."""

    statuses = [
        str(status).casefold()
        for (status,) in db.query(Matchup.status)
        .filter(Matchup.season == season, Matchup.week == week)
        .all()
    ]
    if not statuses or not all(status in FINAL_MATCHUP_STATUSES for status in statuses):
        return False
    # Matchup certification considers starters. Catalog charts also include
    # benched and unrostered players: a known unfinished game cannot become
    # finalized history merely because nobody started one of its players.
    from collegefootballfantasy_api.app.models.game import Game
    from collegefootballfantasy_api.app.services.player_chart_publication import eligible_chart_players_query
    from collegefootballfantasy_api.app.services.fantasy_game_selection import fantasy_games_by_school,school_key
    schools={school_key(p.school) for p in eligible_chart_players_query(db,season).all()}
    games=db.query(Game).filter(Game.season==season,Game.season_type=="regular",Game.week.in_((0,1) if week==1 else (week,))).all()
    selected=fantasy_games_by_school(db,season=season,week=week,games=games)
    known_schools={school_key(team) for game in games if game.week==week for team in (game.home_team,game.away_team)} | set(selected)
    for school in schools & known_schools:
        game=selected.get(school)
        if game is None or (game.schedule_status or "").lower() not in {"final","post"}:
            return False
    return True


def latest_authoritatively_finalized_week(db: Session, *, season: int) -> int:
    """Return the latest uninterrupted finalized fantasy week for ``season``."""

    completed_week = 0
    for week in range(1, MAX_REGULAR_SEASON_WEEK + 1):
        if not week_is_authoritatively_finalized(db, season=season, week=week):
            break
        completed_week = week
    return completed_week
