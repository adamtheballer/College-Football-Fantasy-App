"""Evidence-backed pregame comparisons, independent of mutable live forecasts."""
from sqlalchemy.orm import Session
from datetime import datetime,timezone
import json

from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.player_chart_week import PlayerChartForecast
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school
from collegefootballfantasy_api.app.services.projection_scoring import projection_stats, points_for_projection_inputs


def school_key(name: str) -> str:
    return canonical_school_name(name) or normalize_school(name)


def _forecast_snapshot(player: Player, row: WeeklyProjection, schedule: TeamSchedule) -> dict:
    return {"projection_id": row.id, "position": player.position, "standard_points": row.fantasy_points,
            "stats": projection_stats(row), "projection_version": row.projection_version,
            "projection_status": row.projection_status, "published_at": row.updated_at.isoformat(),
            "kickoff_at": schedule.kickoff_at.isoformat()}


def pregame_forecast(db: Session, *, player: Player, season: int, week: int, schedule: TeamSchedule | None) -> dict | None:
    frozen = db.query(PlayerChartForecast).filter_by(player_id=player.id,season=season,week=week).one_or_none()
    if frozen is not None:
        return frozen.snapshot_json
    # A date without a time cannot certify that a projection preceded kickoff.
    if schedule is None or schedule.kickoff_at is None or schedule.is_bye:
        return None
    row = db.scalar(current_published_projections_query(
        season=season, week=week, player_ids=(player.id,), published_before=schedule.kickoff_at,
    ))
    if row is None:
        return None
    return _forecast_snapshot(player,row,schedule)


def forecast_points(snapshot: dict, scoring_rules: dict | None) -> float | None:
    return points_for_projection_inputs(position=snapshot["position"], standard_points=snapshot["standard_points"], stats=snapshot["stats"], scoring_rules=scoring_rules)


def capture_started_chart_forecasts(db: Session, *, season: int, week: int, now: datetime | None = None, batch_size: int = 200) -> dict:
    """Capture all supported players after kickoff, without changing forecasts.

    Only a source version evidenced before kickoff is accepted. Historical
    recovery uses the same rule and cannot archive a retrospective estimate.
    """
    from collegefootballfantasy_api.app.services.player_chart_publication import eligible_chart_players_query
    from collegefootballfantasy_api.app.services.fantasy_game_selection import fantasy_stat_weeks
    if not 1<=week<=13 or batch_size<1:
        raise ValueError("Chart capture requires fantasy week 1–13 and a positive batch size")
    now = now or datetime.now(timezone.utc)
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    schedules={(school_key(s.team_name),s.week):s for s in db.query(TeamSchedule).filter(TeamSchedule.season==season,TeamSchedule.week.in_((0,1) if week==1 else (week,))).all()}
    from collegefootballfantasy_api.app.models.game import Game
    game_ids={s.game_id for s in schedules.values() if s.game_id is not None}
    blocked_games={g.id for g in db.query(Game).filter(Game.id.in_(game_ids)).all() if g.season!=season or (g.schedule_status or "").lower() in {"postponed","cancelled","canceled","tbd"}}
    result={"eligible":0,"captured":0,"unchanged":0,"started":0,"byes":0,"pending_kickoff":0,"blocked_game_ids":[],"missing_kickoff_ids":[],"unavailable_ids":[],"failures":[]}
    last_id=0
    while True:
        players=eligible_chart_players_query(db,season).filter(Player.id>last_id).order_by(Player.id).limit(batch_size).all()
        if not players: break
        result["eligible"]+=len(players)
        last_id=players[-1].id
        source_weeks=fantasy_stat_weeks(db,season=season,week=week,player_ids={p.id for p in players},player_schools={p.id:p.school for p in players})
        frozen={r.player_id:r for r in db.query(PlayerChartForecast).filter(PlayerChartForecast.player_id.in_([p.id for p in players]),PlayerChartForecast.season==season,PlayerChartForecast.week==week).all()}
        grouped_cutoffs={}
        started={}
        for player in players:
            schedule=schedules.get((school_key(player.school),source_weeks[player.id]))
            if schedule is not None and schedule.game_id in blocked_games:
                result["blocked_game_ids"].append(player.id)
                continue
            if schedule is not None and schedule.is_bye:
                result["byes"]+=1
                continue
            if schedule is None or schedule.kickoff_at is None:
                result["missing_kickoff_ids"].append(player.id)
                continue
            kickoff=schedule.kickoff_at.replace(tzinfo=timezone.utc) if schedule.kickoff_at.tzinfo is None else schedule.kickoff_at.astimezone(timezone.utc)
            if now<kickoff:
                result["pending_kickoff"]+=1
                continue
            started[player.id]=schedule
            if player.id not in frozen:
                grouped_cutoffs.setdefault(kickoff,[]).append(player.id)
        candidates={}
        for kickoff,player_ids in grouped_cutoffs.items():
            candidates.update({r.player_id:r for r in db.scalars(current_published_projections_query(season=season,week=week,player_ids=player_ids,published_before=kickoff)).all()})
        for player in players:
            if player.id not in started: continue
            schedule=started[player.id]
            result["started"]+=1
            try:
                with db.begin_nested():
                    if player.id in frozen:
                        result["unchanged"]+=1
                        continue
                    source=candidates.get(player.id)
                    if source is None:
                        result["unavailable_ids"].append(player.id)
                        continue
                    snapshot=_forecast_snapshot(player,source,schedule)
                    json.dumps(snapshot,allow_nan=False)
                    db.add(PlayerChartForecast(player_id=player.id,season=season,week=week,snapshot_json=snapshot,captured_at=now))
                    db.flush()
                    result["captured"]+=1
            except Exception as exc:
                result["failures"].append({"player_id":player.id,"error":type(exc).__name__})
    result["status"]="partial" if result["blocked_game_ids"] or result["missing_kickoff_ids"] or result["unavailable_ids"] or result["failures"] else "complete"
    return result
