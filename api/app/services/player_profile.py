from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.player import (
    PlayerCardAboutRead,
    PlayerCardInjuryRead,
    PlayerCardStatRowRead,
    PlayerProfileRead,
)
from collegefootballfantasy_api.app.services.player_availability import (
    build_availability_context,
    ownership_percentage,
    player_availability,
)
from collegefootballfantasy_api.app.services.player_search import _injury_read, _projection_dict, _trend_dict


def _local_bio(player: Player) -> PlayerCardAboutRead:
    espn_id = player.external_id
    if espn_id and espn_id.lower().startswith("espn:"):
        espn_id = espn_id.split(":", 1)[1]
    return PlayerCardAboutRead(
        espn_player_id=espn_id,
        player_class=player.player_class,
        position=player.position,
        team=player.school,
        headshot_url=player.image_url,
        source="local",
        message="Local player profile. ESPN profile details are available through the player card endpoint when configured.",
    )


def _schedule_rows(db: Session, *, player: Player, season: int, week: int | None) -> list[dict]:
    query = db.query(Game).filter(
        Game.season == season,
        or_(Game.home_team.ilike(player.school), Game.away_team.ilike(player.school)),
    )
    if week is not None:
        query = query.filter(Game.week >= week)
    rows = query.order_by(Game.week.asc(), Game.start_date.asc()).limit(5).all()
    data: list[dict] = []
    for row in rows:
        opponent = row.away_team if row.home_team == player.school else row.home_team
        data.append(
            {
                "game_id": row.id,
                "season": row.season,
                "week": row.week,
                "opponent": opponent,
                "home_team": row.home_team,
                "away_team": row.away_team,
                "start_date": row.start_date.isoformat() if row.start_date else None,
                "status": "scheduled",
            }
        )
    return data


def _stat_rows(db: Session, *, player_id: int) -> list[PlayerCardStatRowRead]:
    rows = (
        db.query(PlayerStat)
        .filter(PlayerStat.player_id == player_id)
        .order_by(PlayerStat.season.desc(), PlayerStat.week.desc(), PlayerStat.updated_at.desc())
        .limit(20)
        .all()
    )
    return [
        PlayerCardStatRowRead(
            season=row.season,
            week=row.week,
            source=row.source,
            stats=row.stats,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


def _news_rows(injury: Injury | None) -> list[dict]:
    if not injury:
        return []
    title = f"{injury.status}: {injury.injury}" if injury.injury else injury.status
    return [
        {
            "type": "injury",
            "title": title,
            "body": injury.notes,
            "season": injury.season,
            "week": injury.week,
            "status": injury.status,
            "normalized_status": injury.normalized_status,
            "source": injury.source,
            "source_updated_at": injury.source_updated_at.isoformat() if injury.source_updated_at else None,
            "first_seen_at": injury.first_seen_at.isoformat() if injury.first_seen_at else None,
            "last_seen_at": injury.last_seen_at.isoformat() if injury.last_seen_at else None,
            "cleared_at": injury.cleared_at.isoformat() if injury.cleared_at else None,
            "updated_at": injury.updated_at.isoformat() if injury.updated_at else None,
        }
    ]


def build_player_profile(
    db: Session,
    *,
    player: Player,
    current_user,
    league: League | None,
    season: int,
    week: int | None,
) -> PlayerProfileRead:
    target_week = week or 1
    league_id = league.id if league else None
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first() if league_id else None
    scoring_json = settings.scoring_json if settings else None
    context = build_availability_context(db, league_id=league_id, current_user=current_user)
    availability = player_availability(db, player=player, league=league, context=context)
    projection = (
        db.query(WeeklyProjection)
        .filter(WeeklyProjection.player_id == player.id, WeeklyProjection.season == season, WeeklyProjection.week == target_week)
        .first()
    )
    injury = (
        db.query(Injury)
        .filter(Injury.player_id == player.id, Injury.season == season, Injury.week == target_week)
        .order_by(Injury.updated_at.desc())
        .first()
    )
    return PlayerProfileRead(
        player=player,
        bio=_local_bio(player),
        availability=availability,
        ownership_percentage=ownership_percentage(db, player.id, season_year=season),
        watchlisted=player.id in context.watchlisted_player_ids,
        projection=_projection_dict(projection, scoring_json),
        injury=_injury_read(injury),
        schedule=_schedule_rows(db, player=player, season=season, week=week),
        stats=_stat_rows(db, player_id=player.id),
        recent_trend=_trend_dict(db, league_id=league_id, player_id=player.id, season=season, week=target_week),
        news=_news_rows(injury),
    )
