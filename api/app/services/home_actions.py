from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.services.injury_status import reviewed_injuries_for_week, is_current_injury_designation, normalize_injury_status
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week
from collegefootballfantasy_api.app.schemas.product import HomeAction, HomeActions


def home_actions(db: Session, user_id: int) -> HomeActions:
    now = datetime.now(timezone.utc)
    week = calendar_cfb_week(settings.current_season_year, now)
    teams = db.query(Team, League).join(League).filter(Team.owner_user_id == user_id, League.season_year == settings.current_season_year).all()
    team_map = {t.id: (t, l) for t, l in teams}
    rows = db.query(RosterEntry, Player).join(Player).filter(RosterEntry.team_id.in_(team_map)).all() if team_map else []
    starters = [(r,p) for r,p in rows if r.slot.upper() not in {'BENCH','BN','IR','RESERVE'}]
    injuries = reviewed_injuries_for_week(db, season=settings.current_season_year, week=week, player_ids={p.id for _,p in starters})
    actions = []
    for r,p in starters:
        report = injuries.get(p.id)
        if report and is_current_injury_designation(report.status):
            league = team_map[r.team_id][1]
            actions.append(HomeAction(key=f'injury:{r.id}', title=f'{p.name}: {normalize_injury_status(report.status).replace("_", " ").title()}',
                detail=f'{league.name} · review your starting lineup', href=f'/league/{r.league_id}/roster', priority=1))
    schedules = db.query(TeamSchedule).filter(TeamSchedule.season == settings.current_season_year, TeamSchedule.week == week,
        TeamSchedule.is_bye.is_(False), TeamSchedule.kickoff_at > now, TeamSchedule.kickoff_at <= now + timedelta(hours=24)).all()
    by_school = {s.team_name.casefold(): s for s in schedules}
    for t,l in teams:
        upcoming = [by_school[p.school.casefold()] for r,p in starters if r.team_id == t.id and p.school.casefold() in by_school]
        if upcoming:
            lock = min(s.kickoff_at for s in upcoming)
            actions.append(HomeAction(key=f'lock:{t.id}', title='Lineup lock approaching', detail=f'{l.name} · first starter kicks off within 24 hours', href=f'/league/{l.id}/roster', priority=2, deadline=lock))
    trades = db.query(TradeOffer).filter(TradeOffer.receiving_team_id.in_(team_map), TradeOffer.status == 'proposed').order_by(TradeOffer.created_at).all() if team_map else []
    for trade in trades:
        if trade.expires_at and (trade.expires_at.replace(tzinfo=timezone.utc) if trade.expires_at.tzinfo is None else trade.expires_at) <= now:
            continue
        league = team_map[trade.receiving_team_id][1]
        actions.append(HomeAction(key=f'trade:{trade.id}', title='Trade offer to review', detail=league.name,
            href=f'/leagues/{trade.league_id}/trades/{trade.id}', priority=3, deadline=trade.expires_at))
    return HomeActions(data=sorted(actions, key=lambda a:(a.priority,a.key))[:12], checked_at=now)
