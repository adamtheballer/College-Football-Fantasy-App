"""Choose a single scoring game without relabeling or deleting real games.

Fantasy Week 1 includes the opening Week 0 slate. Schools that have already
completed that opener keep it as their sole Week 1 scoring game, even when
they play again before the rest of the opening slate finishes. Week 2 and
later use their normal provider week. Raw ingestion and game logs must not
use this mapping: both real games remain available there.
"""

from datetime import timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.league_weeks import season_week_one_start
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school


def school_key(school: str | None) -> str | None:
    return (canonical_school_name(school) or normalize_school(school)) if school else None


def opening_scoring_games(db: Session, *, season: int, week: int, games: list[Game] | None = None) -> dict[str, Game]:
    if week != 1:
        return {}
    result: dict[str, Game] = {}
    if games is None:
        games = db.query(Game).filter(Game.season == season, Game.week == 0).order_by(Game.start_date, Game.id).all()
    for game in games:
        if game.season != season or game.week != 0 or game.season_type != "regular" or game.schedule_status not in {"final", "post"}:
            continue
        # Ignore empty/import-placeholder schedule rows. Never infer finality
        # from the date alone or pull an old/postseason game into this week.
        if not game.external_id or game.start_date is None:
            continue
        start = game.start_date.replace(tzinfo=timezone.utc) if game.start_date.tzinfo is None else game.start_date
        if start >= season_week_one_start(season):
            continue
        if any((team or "").strip().upper() in {"", "BYE", "TBD"} for team in (game.home_team, game.away_team)):
            continue
        for team in (game.home_team, game.away_team):
            result.setdefault(school_key(team), game)
    return result


def fantasy_stat_weeks(
    db: Session, *, season: int, week: int, player_ids: set[int],
    games: list[Game] | None = None, player_schools: dict[int, str | None] | None = None,
) -> dict[int, int]:
    result = dict.fromkeys(player_ids, week)
    opening = opening_scoring_games(db, season=season, week=week, games=games)
    if opening and player_ids:
        if player_schools is None:
            player_schools = dict(db.query(Player.id, Player.school).filter(Player.id.in_(player_ids)).all())
        for player_id, school in player_schools.items():
            if school_key(school) in opening:
                result[player_id] = 0
    return result


def fantasy_games_by_school(
    db: Session, *, season: int, week: int, games: list[Game] | None = None,
) -> dict[str, Game | None]:
    if games is None:
        games = db.query(Game).filter(Game.season == season, Game.week.in_((0, 1) if week == 1 else (week,))).all()
    result: dict[str, Game | None] = {}
    for game in games:
        if game.week != week:
            continue
        if (game.schedule_status or "").lower() in {"cancelled", "canceled", "postponed", "tbd"}:
            continue
        for team in (game.home_team, game.away_team):
            key = school_key(team)
            if not key:
                continue
            # Ambiguous normal-week schedules remain unavailable for finality.
            if key not in result:
                result[key] = game
            elif result[key] is not None and result[key].external_id != game.external_id:
                result[key] = None
    result.update(opening_scoring_games(db, season=season, week=week, games=games))
    return result
