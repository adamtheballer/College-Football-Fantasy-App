from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.injury_impact import InjuryImpact
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.schemas.injury import InjuryList, InjuryRead
from collegefootballfantasy_api.app.services.power4 import conference_for_school, resolve_power4_school
from collegefootballfantasy_api.app.services.injury_status import reviewed_injuries_for_week, normalize_injury_status
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week

router = APIRouter()


@router.get("", response_model=InjuryList)
def list_injuries(
    season: int | None = Query(default=None, ge=2000, le=2100),
    week: int | None = Query(default=None, ge=1, le=30),
    status: str | None = None,
    team: str | None = None,
    position: str | None = None,
    conference: str | None = None,
    db: Session = Depends(get_db),
) -> InjuryList:
    season = season or datetime.now(timezone.utc).year
    week = week or calendar_cfb_week(season)
    reports = reviewed_injuries_for_week(db, season=season, week=week)
    query = db.query(Player).filter(Player.id.in_(reports))
    if status:
        reports = {key: row for key, row in reports.items() if normalize_injury_status(row.status) == normalize_injury_status(status)}
    if team:
        query = query.filter(Player.school.ilike(f"%{team}%"))
    if position:
        query = query.filter(Player.position == position.upper())
    players = query.all()
    source_urls: dict[tuple[int, int], str] = {}
    if reports:
        events = db.query(PlayerAvailabilityEvent).filter(
            PlayerAvailabilityEvent.player_id.in_(reports),
            PlayerAvailabilityEvent.season == season,
            PlayerAvailabilityEvent.reviewed.is_(True),
            PlayerAvailabilityEvent.source_url.is_not(None),
        ).order_by(PlayerAvailabilityEvent.id.desc()).all()
        for event in events:
            source_urls.setdefault((event.player_id, event.week), event.source_url)

    impacts = {
        impact.player_id: impact.delta_fpts
        for impact in db.query(InjuryImpact)
        .filter(InjuryImpact.season == season, InjuryImpact.week == week)
        .all()
    }

    conference_normalized = conference.upper().replace(" ", "") if conference else None
    data = []
    for player in players:
        injury = reports.get(player.id)
        if injury is None:
            continue
        canonical_team = resolve_power4_school(player.school or "")
        player_conference = conference_for_school(canonical_team or player.school)
        if not player_conference:
            continue
        if conference_normalized and conference_normalized not in {"ALL", "ANY", player_conference}:
            continue
        data.append(
            InjuryRead(
                player_id=player.id,
                player_name=player.name,
                team=canonical_team or player.school,
                conference=player_conference,
                position=player.position,
                season=injury.season,
                week=injury.week,
                status=normalize_injury_status(injury.status),
                injury=injury.injury,
                return_timeline=injury.return_timeline,
                practice_level=injury.practice_level,
                notes=injury.notes,
                last_updated=injury.updated_at or datetime.utcnow(),
                projection_delta=impacts.get(player.id),
                source_url=source_urls.get((player.id, injury.week)),
            )
        )
    return InjuryList(data=data, total=len(data), season=season, week=week)


@router.get("/player/{player_id}", response_model=InjuryRead)
def get_player_injury(
    player_id: int,
    season: int | None = Query(default=None, ge=2000, le=2100),
    week: int | None = Query(default=None, ge=1, le=30),
    db: Session = Depends(get_db),
) -> InjuryRead:
    season = season or datetime.now(timezone.utc).year
    week = week or calendar_cfb_week(season)
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="player not found")
    injury = reviewed_injuries_for_week(db, season=season, week=week, player_ids={player_id}).get(player_id)
    if injury is None:
        return InjuryRead(
            player_id=player_id,
            player_name=player.name,
            team=player.school,
            conference=conference_for_school(player.school),
            position=player.position,
            season=season,
            week=week,
            status="UNREPORTED",
            last_updated=datetime.utcnow(),
            projection_delta=None,
        )
    canonical_team = resolve_power4_school(player.school or "")
    impact = (
        db.query(InjuryImpact)
        .filter(InjuryImpact.player_id == player_id, InjuryImpact.season == season, InjuryImpact.week == week)
        .first()
    )
    return InjuryRead(
        player_id=player.id,
        player_name=player.name,
        team=canonical_team or player.school,
        conference=conference_for_school(canonical_team or player.school),
        position=player.position,
        season=injury.season,
        week=injury.week,
        status=normalize_injury_status(injury.status),
        injury=injury.injury,
        return_timeline=injury.return_timeline,
        practice_level=injury.practice_level,
        notes=injury.notes,
        last_updated=injury.updated_at or datetime.utcnow(),
        projection_delta=impact.delta_fpts if impact else None,
    )
