from __future__ import annotations

from datetime import timezone

from sqlalchemy import and_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent


def confirmed_nonparticipant_ids(db: Session, *, season: int, week: int, player_ids: set[int], reviewed_only: bool = True) -> set[int]:
    """Batch the existing effective-absence rule; a newer FULL clears an old OUT.

    Challenge settlement uses reviewed source assertions only, after game finality.
    An absent box-score row alone never establishes a nonparticipant.
    """
    query = db.query(PlayerAvailabilityEvent).filter(
        PlayerAvailabilityEvent.player_id.in_(player_ids), PlayerAvailabilityEvent.season == season,
        PlayerAvailabilityEvent.effective_from_week <= week,
        (PlayerAvailabilityEvent.effective_until_week.is_(None)) | (PlayerAvailabilityEvent.effective_until_week >= week),
    )
    if reviewed_only:
        query = query.filter(PlayerAvailabilityEvent.reviewed.is_(True))
    latest: dict[int, PlayerAvailabilityEvent] = {}
    for row in query.order_by(PlayerAvailabilityEvent.created_at.desc(), PlayerAvailabilityEvent.id.desc()):
        latest.setdefault(row.player_id, row)
    return {pid for pid, row in latest.items() if row.status.upper() in {"OUT", "SUSPENDED", "INELIGIBLE", "OUT_FOR_SEASON"} and bool(row.source)}


def reviewed_injuries_for_week(
    db: Session, *, season: int, week: int, player_ids: set[int] | None = None
) -> dict[int, Injury]:
    """Newest weekly report plus persistent, already-effective season absences.

    Select a row before interpreting its status so a newer FULL report clears
    an older OUT row. Never carry ordinary weekly injuries into a later week.
    """
    if player_ids == set():
        return {}
    from collegefootballfantasy_api.app.services.availability_corrections import MANUAL_VERIFIED_SOURCES
    # Keep this a single bounded query for the roster/matchup read budget.
    query = db.query(Injury, PlayerAvailabilityEvent).outerjoin(
        PlayerAvailabilityEvent,
        and_(
            PlayerAvailabilityEvent.player_id == Injury.player_id,
            PlayerAvailabilityEvent.season == season,
            PlayerAvailabilityEvent.reviewed.is_(True),
            PlayerAvailabilityEvent.source.in_(MANUAL_VERIFIED_SOURCES),
            PlayerAvailabilityEvent.source_url.is_not(None),
            PlayerAvailabilityEvent.effective_from_week <= week,
            PlayerAvailabilityEvent.effective_until_week >= week,
        ),
    ).filter(Injury.season == season, Injury.week <= week)
    if player_ids is not None:
        query = query.filter(Injury.player_id.in_(player_ids))
    pairs = query.order_by(Injury.week.desc(), Injury.updated_at.desc(), Injury.id.desc(),
                           PlayerAvailabilityEvent.created_at.desc(), PlayerAvailabilityEvent.id.desc()).all()
    rows_by_id = {}
    events: dict[int, PlayerAvailabilityEvent] = {}
    for row, event in pairs:
        rows_by_id.setdefault(row.id, row)
        if event is not None:
            events.setdefault(event.player_id, event)
    rows = list(rows_by_id.values())
    latest: dict[int, Injury] = {}
    for row in rows:
        latest.setdefault(row.player_id, row)
    # Interpret the latest report, not any historical season-ending row. A
    # subsequently verified return must clear an old season absence.
    # A subsequent weekly OUT repeats the absence; only a different later
    # designation can clear the confirmed season-ending report.
    season_absences = {}
    settled = set()
    for row in rows:
        if row.player_id in settled or normalize_injury_status(row.status) == "OUT":
            continue
        settled.add(row.player_id)
        if normalize_injury_status(row.status) == "OUT_FOR_SEASON":
            season_absences[row.player_id] = row
    current = {pid: row for pid, row in latest.items()
               if row.week == week or normalize_injury_status(row.status) == "OUT_FOR_SEASON"}

    current.update(season_absences)

    for pid, event in events.items():
        report = latest.get(pid)
        # Explicit later-week reports supersede older corroborated assertions;
        # an absence cannot become permanent or defeat a verified return.
        if report is not None:
            status = normalize_injury_status(report.status)
            event_status = normalize_injury_status(event.status)
            repeated_absence = status == event_status or (status == "OUT" and event_status == "OUT_FOR_SEASON")
            if report.week > event.week and not repeated_absence:
                continue
            if (report.week == event.week and report.updated_at and event.created_at
                and report.updated_at.replace(tzinfo=timezone.utc) > event.created_at.replace(tzinfo=timezone.utc)
                and normalize_injury_status(report.status) != normalize_injury_status(event.status)):
                continue
        source = next((r for r in rows if r.player_id == pid and r.week == event.week
                       and normalize_injury_status(r.status) == normalize_injury_status(event.status)), None)
        if source is not None:
            current[pid] = source
    return current


def normalize_injury_status(raw_status: str | None) -> str:
    """Return the canonical reviewed-injury designation used by all API readers."""
    status = " ".join((raw_status or "FULL").strip().upper().replace("_", " ").replace("-", " ").split())

    if status in {"", "FULL", "HEALTHY", "ACTIVE", "AVAILABLE"}:
        return "FULL"
    if status in {"N/A", "N A", "NA", "NOT APPLICABLE"}:
        return "N_A"
    if status in {"TBD", "TO BE DETERMINED"}:
        return "TBD"
    if any(token in status for token in ("OUT FOR SEASON", "SEASON ENDING", "SEASON END", "LOST FOR THE SEASON")):
        return "OUT_FOR_SEASON"
    if "DAY TO DAY" in status:
        return "DAY_TO_DAY"
    if "SUSPEND" in status:
        return "SUSPENDED"
    if "INACTIVE" in status:
        return "INACTIVE"
    if status == "IR" or "INJURED RESERVE" in status:
        return "IR"
    if "OUT" in status:
        return "OUT"
    if "DOUBTFUL" in status:
        return "DOUBTFUL"
    if "QUESTION" in status or "GTD" in status or "GAME TIME" in status:
        return "QUESTIONABLE"
    if "PROBABLE" in status:
        return "PROBABLE"
    return "TBD"


def is_current_injury_designation(status: str | None) -> bool:
    """Whether a normalized status is an active, informational injury designation."""
    return normalize_injury_status(status) not in {"FULL", "N_A"}


def is_out_for_season(db: Session, *, player_id: int, season: int) -> bool:
    """Whether a reviewed season-ending report applies to the player.

    Unlike a normal weekly status, this designation remains active after the
    week that recorded it so acquisition and roster reads stay consistent.
    """
    from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week
    report = reviewed_injuries_for_week(
        db, player_ids={player_id}, season=season, week=calendar_cfb_week(season),
    ).get(player_id)
    return report is not None and normalize_injury_status(report.status) == "OUT_FOR_SEASON"
