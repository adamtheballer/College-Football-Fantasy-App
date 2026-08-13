"""Rivalry selection and server-derived Rival Week context."""

from __future__ import annotations

from datetime import timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.career import LeagueRivalry
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.postseason import PostseasonMatchup, PostseasonRound
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.career import CareerRecordRead, RivalCandidateRead, RivalryMatchupRead, RivalryRead
from collegefootballfantasy_api.app.services.career_profile import FINAL_MATCHUP_STATUSES, record_career_event, utcnow

RIVAL_CHANGE_COOLDOWN = timedelta(days=7)


def _owned_team(db: Session, league: League, user: User) -> Team:
    team = db.query(Team).filter(Team.league_id == league.id, Team.owner_user_id == user.id).one_or_none()
    if team is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="a human-managed team is required to set a rival")
    return team


def _candidates(db: Session, league_id: int, own_team_id: int) -> list[RivalCandidateRead]:
    rows = db.query(Team).filter(Team.league_id == league_id, Team.owner_user_id.is_not(None), Team.id != own_team_id).order_by(Team.name).all()
    return [RivalCandidateRead(team_id=row.id, team_name=row.name, manager_name=row.owner_name or "Manager") for row in rows]


def _completed_rivalry_matchup_exists(db: Session, rivalry: LeagueRivalry) -> bool:
    return db.query(Matchup.id).filter(
        Matchup.league_id == rivalry.league_id,
        Matchup.season == rivalry.season,
        func.lower(Matchup.status).in_(FINAL_MATCHUP_STATUSES),
        ((Matchup.home_team_id == rivalry.team_id) & (Matchup.away_team_id == rivalry.rival_team_id))
        | ((Matchup.home_team_id == rivalry.rival_team_id) & (Matchup.away_team_id == rivalry.team_id)),
    ).first() is not None


def _can_change(db: Session, rivalry: LeagueRivalry | None) -> bool:
    if rivalry is None or not _completed_rivalry_matchup_exists(db, rivalry):
        return True
    changed_at = rivalry.changed_at or rivalry.selected_at
    # PostgreSQL preserves the timezone on this column, while SQLite test
    # databases return a naive value. Treat a naive persisted timestamp as UTC
    # so the cooldown has identical semantics in both environments.
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)
    else:
        changed_at = changed_at.astimezone(timezone.utc)
    return utcnow() >= changed_at + RIVAL_CHANGE_COOLDOWN


def get_rivalry(db: Session, league: League, user: User) -> RivalryRead:
    team = _owned_team(db, league, user)
    rivalry = db.query(LeagueRivalry).filter(
        LeagueRivalry.league_id == league.id, LeagueRivalry.season == league.season_year,
        LeagueRivalry.team_id == team.id, LeagueRivalry.active.is_(True),
    ).one_or_none()
    rival = db.get(Team, rivalry.rival_team_id) if rivalry else None
    return RivalryRead(
        league_id=league.id, season=league.season_year, team_id=team.id,
        rival_team_id=rival.id if rival else None, rival_team_name=rival.name if rival else None,
        rival_manager_name=(rival.owner_name or "Manager") if rival else None,
        selected_at=rivalry.selected_at if rivalry else None, changed_at=rivalry.changed_at if rivalry else None,
        can_change=_can_change(db, rivalry), candidates=_candidates(db, league.id, team.id),
    )


def set_rivalry(db: Session, league: League, user: User, rival_team_id: int) -> RivalryRead:
    team = _owned_team(db, league, user)
    rival = db.query(Team).filter(Team.id == rival_team_id, Team.league_id == league.id, Team.owner_user_id.is_not(None)).one_or_none()
    if rival is None or rival.id == team.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="select another human-managed team in this league")
    rivalry = db.query(LeagueRivalry).filter(
        LeagueRivalry.league_id == league.id, LeagueRivalry.season == league.season_year, LeagueRivalry.team_id == team.id,
    ).one_or_none()
    if rivalry and rivalry.rival_team_id == rival.id:
        return get_rivalry(db, league, user)
    now = utcnow()
    if rivalry is not None and not _can_change(db, rivalry):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="your rival can change once the seven-day Rival Week cooldown ends")
    if rivalry is None:
        rivalry = LeagueRivalry(league_id=league.id, season=league.season_year, team_id=team.id, rival_team_id=rival.id, selected_by_user_id=user.id, selected_at=now, active=True)
        event_type, source_key, title = "RIVAL_SELECTED", f"rival:selected:{league.id}:{league.season_year}:{team.id}:{rival.id}", f"Selected {rival.name} as your rival"
        db.add(rivalry)
    else:
        previous = rivalry.rival_team_id
        rivalry.rival_team_id = rival.id
        rivalry.changed_at = now
        rivalry.rivalry_version += 1
        event_type, source_key, title = "RIVAL_CHANGED", f"rival:changed:{league.id}:{league.season_year}:{team.id}:{rival.id}:{rivalry.rivalry_version}", f"Changed rival to {rival.name}"
        if previous == rival.id:
            return get_rivalry(db, league, user)
    record_career_event(db, user_id=user.id, event_type=event_type, source_key=source_key, title=title, league_id=league.id, team_id=team.id, season=league.season_year, metadata={"rival_team_id": rival.id})
    db.commit()
    return get_rivalry(db, league, user)


def _series(db: Session, league: League, team_id: int, rival_team_id: int) -> tuple[CareerRecordRead, Matchup | None]:
    rows = db.query(Matchup).filter(
        Matchup.league_id == league.id, Matchup.season == league.season_year,
        ((Matchup.home_team_id == team_id) & (Matchup.away_team_id == rival_team_id))
        | ((Matchup.home_team_id == rival_team_id) & (Matchup.away_team_id == team_id)),
    ).order_by(Matchup.week, Matchup.id).all()
    wins = losses = ties = 0
    completed = [row for row in rows if (row.status or "").lower() in FINAL_MATCHUP_STATUSES]
    for row in completed:
        own_score, rival_score = (row.home_score, row.away_score) if row.home_team_id == team_id else (row.away_score, row.home_score)
        if own_score > rival_score: wins += 1
        elif own_score < rival_score: losses += 1
        else: ties += 1
    total = wins + losses + ties
    return CareerRecordRead(wins=wins, losses=losses, ties=ties, win_pct=round((wins + ties * .5) / total, 3) if total else 0.0), (completed[-1] if completed else None)


def rivalry_matchup_context(db: Session, league: League, user: User, matchup: Matchup) -> RivalryMatchupRead:
    team = _owned_team(db, league, user)
    championship = db.query(PostseasonMatchup.id).join(
        PostseasonRound, PostseasonRound.id == PostseasonMatchup.round_id
    ).filter(
        PostseasonMatchup.fantasy_matchup_id == matchup.id,
        func.upper(PostseasonRound.round_type) == "CHAMPIONSHIP",
    ).first() is not None
    rivalry = db.query(LeagueRivalry).filter(LeagueRivalry.league_id == league.id, LeagueRivalry.season == league.season_year, LeagueRivalry.team_id == team.id, LeagueRivalry.active.is_(True)).one_or_none()
    if rivalry is None:
        return RivalryMatchupRead(matchup_id=matchup.id, is_rivalry_matchup=False, is_championship=championship, user_team_name=team.name, series=CareerRecordRead())
    rival = db.get(Team, rivalry.rival_team_id)
    if rival is None:
        return RivalryMatchupRead(
            matchup_id=matchup.id,
            is_rivalry_matchup=False,
            is_championship=championship,
            user_team_name=team.name,
            series=CareerRecordRead(),
        )
    is_rivalry = {matchup.home_team_id, matchup.away_team_id} == {team.id, rival.id}
    series, last = _series(db, league, team.id, rival.id)
    last_meeting = None
    if last:
        own_score, rival_score = (last.home_score, last.away_score) if last.home_team_id == team.id else (last.away_score, last.home_score)
        last_meeting = {"week": last.week, "own_score": own_score, "rival_score": rival_score, "result": "W" if own_score > rival_score else "L" if own_score < rival_score else "T"}
    return RivalryMatchupRead(matchup_id=matchup.id, is_rivalry_matchup=is_rivalry, is_championship=championship, user_team_name=team.name, rival_team_name=rival.name, series=series, last_meeting=last_meeting)
