from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.injury import Injury, InjuryHistory
from collegefootballfantasy_api.app.models.injury_impact import InjuryImpact
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.schemas.injury import InjuryHistoryRead, InjuryList, InjuryRead
from collegefootballfantasy_api.app.services.power4 import conference_for_school, resolve_power4_school

router = APIRouter()


def _history_rows(db: Session, *, player_id: int, season: int, week: int) -> list[InjuryHistoryRead]:
    rows = (
        db.query(InjuryHistory)
        .filter(InjuryHistory.player_id == player_id, InjuryHistory.season == season, InjuryHistory.week == week)
        .order_by(InjuryHistory.created_at.desc(), InjuryHistory.id.desc())
        .limit(25)
        .all()
    )
    return [
        InjuryHistoryRead(
            id=row.id,
            season=row.season,
            week=row.week,
            status=row.status,
            normalized_status=row.normalized_status,
            injury=row.injury,
            body_part=row.body_part,
            source=row.source,
            source_updated_at=row.source_updated_at,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _injury_read(
    db: Session,
    *,
    injury: Injury,
    player: Player,
    impact: InjuryImpact | None,
) -> InjuryRead:
    canonical_team = resolve_power4_school(player.school or "")
    return InjuryRead(
        player_id=player.id,
        player_name=player.name,
        team=canonical_team or player.school,
        conference=conference_for_school(canonical_team or player.school),
        position=player.position,
        season=injury.season,
        week=injury.week,
        status=injury.status,
        normalized_status=injury.normalized_status,
        injury=injury.injury,
        body_part=injury.body_part,
        return_timeline=injury.return_timeline,
        practice_level=injury.practice_level,
        notes=injury.notes,
        source=injury.source,
        source_updated_at=injury.source_updated_at,
        first_seen_at=injury.first_seen_at,
        last_seen_at=injury.last_seen_at,
        cleared_at=injury.cleared_at,
        last_updated=injury.updated_at or datetime.utcnow(),
        projection_delta=impact.delta_fpts if impact else None,
        projection_multiplier=impact.multiplier if impact else None,
        impact_confidence=impact.confidence if impact else None,
        impact_reason=impact.reason if impact else None,
        history=_history_rows(db, player_id=player.id, season=injury.season, week=injury.week),
    )


@router.get("", response_model=InjuryList)
def list_injuries(
    season: int,
    week: int,
    status: str | None = None,
    team: str | None = None,
    position: str | None = None,
    conference: str | None = None,
    db: Session = Depends(get_db),
) -> InjuryList:
    query = db.query(Injury, Player).join(Player, Injury.player_id == Player.id)
    query = query.filter(Injury.season == season, Injury.week == week)
    if status:
        query = query.filter(Injury.status == status.upper())
    if team:
        query = query.filter(Player.school.ilike(f"%{team}%"))
    if position:
        query = query.filter(Player.position == position.upper())
    rows = query.all()

    impacts = {
        impact.player_id: impact
        for impact in db.query(InjuryImpact)
        .filter(InjuryImpact.season == season, InjuryImpact.week == week)
        .all()
    }

    conference_normalized = conference.upper().replace(" ", "") if conference else None
    data = []
    for injury, player in rows:
        canonical_team = resolve_power4_school(player.school or "")
        player_conference = conference_for_school(canonical_team or player.school)
        if not player_conference:
            continue
        if conference_normalized and conference_normalized != player_conference:
            continue
        data.append(_injury_read(db, injury=injury, player=player, impact=impacts.get(player.id)))
    return InjuryList(data=data, total=len(data))


@router.get("/player/{player_id}", response_model=InjuryRead)
def get_player_injury(
    player_id: int,
    season: int,
    week: int,
    db: Session = Depends(get_db),
) -> InjuryRead:
    row = (
        db.query(Injury, Player)
        .join(Player, Injury.player_id == Player.id)
        .filter(Injury.player_id == player_id, Injury.season == season, Injury.week == week)
        .first()
    )
    if not row:
        return InjuryRead(
            player_id=player_id,
            player_name="Unknown",
            team="Unknown",
            conference=None,
            position="Unknown",
            season=season,
            week=week,
            status="HEALTHY",
            normalized_status="healthy",
            last_updated=datetime.utcnow(),
            projection_delta=None,
        )
    injury, player = row
    canonical_team = resolve_power4_school(player.school or "")
    impact = (
        db.query(InjuryImpact)
        .filter(InjuryImpact.player_id == player_id, InjuryImpact.season == season, InjuryImpact.week == week)
        .first()
    )
    return _injury_read(db, injury=injury, player=player, impact=impact)
