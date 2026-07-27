"""Invariant-enforced Saturday Pick 6 contest workflow.

This service is the only writer for contest state.  It intentionally keeps
selection, locking, scoring, and reward authorization on the server so a
browser cannot bypass the same-position or deadline rules.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.saturday_pick import (
    SaturdayPickContest,
    SaturdayPickEntry,
    SaturdayPickPlayer,
    SponsorRewardEvent,
)
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.saturday_pick import (
    SaturdayPickContestCreate,
    SaturdayPickContestRead,
    SaturdayPickEntryRead,
    SaturdayPickPlayerRead,
    SaturdayPickSponsorRead,
)
from collegefootballfantasy_api.app.domain.scoring_engine import calculate_player_fantasy_points
from collegefootballfantasy_api.app.domain.scoring_rules import default_rules_bundle
from collegefootballfantasy_api.app.domain.stat_normalization import normalize_player_stats


PUBLIC_POSITIONS = ("QB", "RB", "WR", "TE")
DEFAULT_ROTATION = PUBLIC_POSITIONS
FINAL_GAME_STATUSES = {"FINAL", "STAT_CORRECTED"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def canonical_position(raw_position: str | None) -> str | None:
    normalized = (raw_position or "").strip().upper()
    if normalized.startswith("QB"):
        return "QB"
    if normalized.startswith("RB") or normalized in {"HB", "TB", "FB"}:
        return "RB"
    if normalized.startswith("WR"):
        return "WR"
    if normalized.startswith("TE"):
        return "TE"
    return None


def recommended_position(week_number: int) -> str:
    return DEFAULT_ROTATION[(week_number - 1) % len(DEFAULT_ROTATION)]


def _eligible_schedule(db: Session, player: Player, season: int, week: int) -> TeamSchedule:
    schedule = (
        db.query(TeamSchedule)
        .filter(
            TeamSchedule.team_name == player.school,
            TeamSchedule.season == season,
            TeamSchedule.week == week,
        )
        .one_or_none()
    )
    if not schedule or schedule.is_bye or schedule.location == "bye":
        raise ValueError(f"{player.name} does not have an eligible scheduled game.")
    if not schedule.opponent_name:
        raise ValueError(f"{player.name} is missing a verified opponent.")
    if not schedule.kickoff_at:
        raise ValueError(f"{player.name} is missing a verified kickoff time.")
    return schedule


def _is_known_out(db: Session, player_id: int, season: int, week: int) -> bool:
    return (
        db.query(PlayerAvailabilityEvent.id)
        .filter(
            PlayerAvailabilityEvent.player_id == player_id,
            PlayerAvailabilityEvent.season == season,
            PlayerAvailabilityEvent.status.in_(("OUT", "SUSPENDED", "INELIGIBLE")),
            PlayerAvailabilityEvent.effective_from_week <= week,
            (PlayerAvailabilityEvent.effective_until_week.is_(None))
            | (PlayerAvailabilityEvent.effective_until_week >= week),
        )
        .first()
        is not None
    )


def _weekly_projection(db: Session, player_id: int, season: int, week: int) -> float | None:
    projection = (
        db.query(WeeklyProjection)
        .filter(
            WeeklyProjection.player_id == player_id,
            WeeklyProjection.season == season,
            WeeklyProjection.week == week,
            WeeklyProjection.is_published.is_(True),
        )
        .one_or_none()
    )
    return float(projection.fantasy_points) if projection and projection.fantasy_points is not None else None


def _validate_featured_players(
    db: Session,
    *,
    payload: SaturdayPickContestCreate,
) -> list[tuple[Player, TeamSchedule]]:
    player_ids = payload.featured_player_ids
    if len(player_ids) != 6:
        raise ValueError("Saturday Pick 6 must contain exactly six featured players.")
    if len(set(player_ids)) != 6:
        raise ValueError("A featured player cannot appear twice in the same contest.")
    if payload.contest_position not in PUBLIC_POSITIONS:
        raise ValueError("Saturday Pick 6 supports QB, RB, WR, and TE contests only.")
    players = db.query(Player).filter(Player.id.in_(player_ids)).all()
    player_by_id = {player.id: player for player in players}
    if len(player_by_id) != 6:
        raise ValueError("Every featured player must have a canonical player identity.")
    validated: list[tuple[Player, TeamSchedule]] = []
    for player_id in player_ids:
        player = player_by_id[player_id]
        if canonical_position(player.position) != payload.contest_position:
            raise ValueError("All six featured players must match the contest position.")
        if _is_known_out(db, player.id, payload.season, payload.week_number):
            raise ValueError(f"{player.name} is unavailable for this contest.")
        validated.append((player, _eligible_schedule(db, player, payload.season, payload.week_number)))
    return validated


def create_contest(db: Session, payload: SaturdayPickContestCreate, actor: User) -> SaturdayPickContest:
    if db.query(SaturdayPickContest.id).filter(
        SaturdayPickContest.season == payload.season,
        SaturdayPickContest.week_number == payload.week_number,
    ).first():
        raise ValueError("A Saturday Pick 6 contest already exists for this season and week.")
    featured = _validate_featured_players(db, payload=payload)
    earliest_kickoff = min(as_utc(schedule.kickoff_at) for _, schedule in featured)
    lock_at = as_utc(payload.lock_at) if payload.lock_at else earliest_kickoff
    if lock_at > earliest_kickoff:
        raise ValueError("Lock time cannot be later than the earliest featured kickoff.")
    if payload.position_overridden and not payload.override_reason:
        raise ValueError("A manual position override requires an audit reason.")
    contest = SaturdayPickContest(
        season=payload.season,
        week_number=payload.week_number,
        title=payload.title.strip() or "Saturday Pick 6",
        contest_position=payload.contest_position,
        status="DRAFT",
        lock_at=lock_at,
        scoring_policy_version=payload.scoring_policy_version.strip() or "STANDARD_V1",
        sponsor_name=payload.sponsor_name,
        sponsor_logo_url=payload.sponsor_logo_url,
        sponsor_offer_text=payload.sponsor_offer_text,
        sponsor_code=payload.sponsor_code,
        sponsor_url=payload.sponsor_url,
        sponsor_terms=payload.sponsor_terms,
        position_overridden=payload.position_overridden,
        override_reason=payload.override_reason,
        position_override_actor_id=actor.id if payload.position_overridden else None,
        position_overridden_at=utc_now() if payload.position_overridden else None,
        created_by_user_id=actor.id,
    )
    db.add(contest)
    db.flush()
    for sort_order, (player, schedule) in enumerate(featured, start=1):
        db.add(
            SaturdayPickPlayer(
                contest_id=contest.id,
                player_id=player.id,
                canonical_position=payload.contest_position,
                player_name_snapshot=player.name,
                school_snapshot=player.school,
                opponent_snapshot=schedule.opponent_name or "",
                game_id=schedule.game_id,
                game_time=as_utc(schedule.kickoff_at),
                projected_points=_weekly_projection(db, player.id, payload.season, payload.week_number),
                scoring_status="SCHEDULED",
                sort_order=sort_order,
            )
        )
    db.flush()
    return contest


def publish_contest(db: Session, contest: SaturdayPickContest) -> SaturdayPickContest:
    if contest.status not in {"DRAFT", "SCHEDULED"}:
        raise ValueError("Only draft contests can be published.")
    players = db.query(SaturdayPickPlayer).filter(SaturdayPickPlayer.contest_id == contest.id).all()
    if len(players) != 6 or {player.canonical_position for player in players} != {contest.contest_position}:
        raise ValueError("Publication requires exactly six players at the contest position.")
    if min(as_utc(player.game_time) for player in players) < as_utc(contest.lock_at):
        raise ValueError("Contest lock time cannot be after a featured kickoff.")
    contest.status = "OPEN" if utc_now() < as_utc(contest.lock_at) else "LOCKED"
    contest.published_at = utc_now()
    contest.locked_at = utc_now() if contest.status == "LOCKED" else None
    db.flush()
    return contest


def synchronize_lock(contest: SaturdayPickContest) -> None:
    if contest.status == "OPEN" and utc_now() >= as_utc(contest.lock_at):
        contest.status = "LOCKED"
        contest.locked_at = utc_now()


def save_entry(db: Session, contest: SaturdayPickContest, user: User, selected_pick_player_id: int) -> SaturdayPickEntry:
    synchronize_lock(contest)
    if contest.status != "OPEN" or utc_now() >= as_utc(contest.lock_at):
        raise ValueError("Saturday Pick 6 is locked.")
    selected = db.get(SaturdayPickPlayer, selected_pick_player_id)
    if not selected or selected.contest_id != contest.id:
        raise ValueError("Selected player is not featured in this contest.")
    entry = (
        db.query(SaturdayPickEntry)
        .filter(SaturdayPickEntry.contest_id == contest.id, SaturdayPickEntry.user_id == user.id)
        .one_or_none()
    )
    if entry:
        entry.selected_pick_player_id = selected.id
        entry.submitted_at = utc_now()
    else:
        entry = SaturdayPickEntry(
            contest_id=contest.id,
            user_id=user.id,
            selected_pick_player_id=selected.id,
            submitted_at=utc_now(),
        )
        db.add(entry)
    db.flush()
    return entry


def _score_featured_player(db: Session, contest: SaturdayPickContest, featured: SaturdayPickPlayer) -> float | None:
    game = db.get(Game, featured.game_id) if featured.game_id else None
    game_final = bool(game and game.home_points is not None and game.away_points is not None)
    if not game_final:
        return None
    stat = (
        db.query(PlayerGameStat)
        .filter(PlayerGameStat.player_id == featured.player_id, PlayerGameStat.game_id == game.id)
        .one_or_none()
    )
    stat = stat or (
        db.query(PlayerStat)
        .filter(
            PlayerStat.player_id == featured.player_id,
            PlayerStat.season == contest.season,
            PlayerStat.week == contest.week_number,
            PlayerStat.verified.is_(True),
        )
        .one_or_none()
    )
    if not stat:
        return None
    points, _ = calculate_player_fantasy_points(
        normalize_player_stats(stat.stats, featured.canonical_position),
        default_rules_bundle(),
        featured.canonical_position,
    )
    return points


def finalize_contest(db: Session, contest: SaturdayPickContest) -> SaturdayPickContest:
    if contest.status == "FINAL":
        return contest
    synchronize_lock(contest)
    featured = (
        db.query(SaturdayPickPlayer)
        .filter(SaturdayPickPlayer.contest_id == contest.id)
        .order_by(SaturdayPickPlayer.sort_order.asc())
        .all()
    )
    if len(featured) != 6:
        raise ValueError("Cannot finalize a contest without six featured players.")
    final_points: list[float] = []
    for row in featured:
        points = _score_featured_player(db, contest, row)
        if points is None:
            raise ValueError("Cannot finalize until every featured game and verified stat line is resolved.")
        row.final_points = points
        row.scoring_status = "FINAL"
        final_points.append(points)
    highest = max(final_points)
    winning_ids = [row.player_id for row in featured if row.final_points == highest]
    contest.status = "PROVISIONAL"
    contest.winning_player_ids_json = winning_ids
    now = utc_now()
    winning_featured_ids = {row.id for row in featured if row.player_id in winning_ids}
    entries = db.query(SaturdayPickEntry).filter(SaturdayPickEntry.contest_id == contest.id).all()
    for entry in entries:
        entry.is_winner = entry.selected_pick_player_id in winning_featured_ids
        entry.winner_determined_at = now
        entry.reward_unlocked_at = now if entry.is_winner and contest.sponsor_name else None
        if entry.is_winner and contest.sponsor_name:
            db.add(SponsorRewardEvent(
                contest_id=contest.id,
                user_id=entry.user_id,
                event_type="reward_unlocked",
                sponsor_name=contest.sponsor_name,
                placement="contest_finalization",
                metadata_json={"winning_player_ids": winning_ids},
            ))
    contest.status = "FINAL"
    contest.finalized_at = now
    db.flush()
    return contest


def contest_read(db: Session, contest: SaturdayPickContest, viewer: User | None = None) -> SaturdayPickContestRead:
    synchronize_lock(contest)
    rows = (
        db.query(SaturdayPickPlayer)
        .filter(SaturdayPickPlayer.contest_id == contest.id)
        .order_by(SaturdayPickPlayer.sort_order.asc())
        .all()
    )
    entry = None
    if viewer:
        entry = db.query(SaturdayPickEntry).filter(
            SaturdayPickEntry.contest_id == contest.id,
            SaturdayPickEntry.user_id == viewer.id,
        ).one_or_none()
    entry_read = SaturdayPickEntryRead(
        id=entry.id,
        selected_pick_player_id=entry.selected_pick_player_id,
        submitted_at=entry.submitted_at,
        is_winner=entry.is_winner,
        reward_unlocked_at=entry.reward_unlocked_at,
    ) if entry else None
    sponsor = None
    if contest.sponsor_name:
        unlocked = bool(entry and entry.is_winner and contest.status == "FINAL")
        sponsor = SaturdayPickSponsorRead(
            name=contest.sponsor_name,
            logo_url=contest.sponsor_logo_url,
            offer_text=contest.sponsor_offer_text,
            terms=contest.sponsor_terms,
            reward_unlocked=unlocked,
            code=contest.sponsor_code if unlocked else None,
            url=contest.sponsor_url if unlocked else None,
        )
    return SaturdayPickContestRead(
        id=contest.id,
        season=contest.season,
        week_number=contest.week_number,
        title=contest.title,
        contest_position=contest.contest_position,
        status=contest.status,
        lock_at=contest.lock_at,
        scoring_policy_version=contest.scoring_policy_version,
        winning_player_ids=contest.winning_player_ids_json or [],
        position_overridden=contest.position_overridden,
        override_reason=contest.override_reason,
        published_at=contest.published_at,
        locked_at=contest.locked_at,
        finalized_at=contest.finalized_at,
        players=[
            SaturdayPickPlayerRead(
                id=row.id,
                player_id=row.player_id,
                canonical_position=row.canonical_position,
                player_name=row.player_name_snapshot,
                school=row.school_snapshot,
                opponent=row.opponent_snapshot,
                game_id=row.game_id,
                game_time=row.game_time,
                projected_points=row.projected_points,
                final_points=row.final_points,
                scoring_status=row.scoring_status,
                sort_order=row.sort_order,
            )
            for row in rows
        ],
        entry=entry_read,
        sponsor=sponsor,
    )
