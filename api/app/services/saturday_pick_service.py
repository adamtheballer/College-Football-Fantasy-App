"""Invariant-enforced Saturday Pick 6 contest workflow.

This service is the only writer for contest state.  It intentionally keeps
selection, locking, scoring, and reward authorization on the server so a
browser cannot bypass the same-position or deadline rules.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
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
    SaturdayPickLockPlayerRead,
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
    if payload.lock_at is not None and as_utc(payload.lock_at) != earliest_kickoff:
        raise ValueError("Saturday Pick 6 locks exactly at the first featured player's kickoff.")
    lock_at = earliest_kickoff
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
    first_kickoff = min(as_utc(player.game_time) for player in players)
    if as_utc(contest.lock_at) != first_kickoff:
        raise ValueError("Saturday Pick 6 locks exactly at the first featured player's kickoff.")
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


def _featured_stat(db: Session, contest: SaturdayPickContest, featured: SaturdayPickPlayer) -> PlayerGameStat | PlayerStat | None:
    game = db.get(Game, featured.game_id) if featured.game_id else None
    stat = (
        db.query(PlayerGameStat)
        .filter(PlayerGameStat.player_id == featured.player_id, PlayerGameStat.game_id == game.id)
        .one_or_none()
        if game
        else None
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
    return stat


def _score_stat(stat: PlayerGameStat | PlayerStat | None, position: str) -> float | None:
    if stat is None:
        return None
    points, _ = calculate_player_fantasy_points(
        normalize_player_stats(stat.stats, position),
        default_rules_bundle(),
        position,
    )
    return points


def _is_final_game(game: Game | None) -> bool:
    return bool(game and game.home_points is not None and game.away_points is not None)


def _featured_scoring_status(*, featured: SaturdayPickPlayer, game: Game | None, has_stats: bool, now: datetime) -> str:
    if _is_final_game(game):
        return "FINAL" if has_stats else "DATA_DELAYED"
    if as_utc(featured.game_time) > now:
        return "NOT_STARTED"
    if has_stats:
        return "LIVE"
    return "DATA_DELAYED"


def refresh_contest_live_scores(db: Session, contest: SaturdayPickContest) -> dict[str, int]:
    """Refresh live Pick 6 scoring from the canonical game-stat records.

    Missing provider data is intentionally represented as ``DATA_DELAYED`` and
    never converted to a zero-point score.  Finalization remains a separate,
    explicitly-administered operation after every featured game is final.
    """

    if contest.status == "FINAL":
        return {"updated": 0, "live": 0, "final": 6}

    synchronize_lock(contest)
    now = utc_now()
    rows = (
        db.query(SaturdayPickPlayer)
        .filter(SaturdayPickPlayer.contest_id == contest.id)
        .order_by(SaturdayPickPlayer.sort_order.asc())
        .all()
    )
    updated = 0
    live = 0
    final = 0
    for row in rows:
        game = db.get(Game, row.game_id) if row.game_id else None
        stat = _featured_stat(db, contest, row)
        points = _score_stat(stat, row.canonical_position)
        next_status = _featured_scoring_status(featured=row, game=game, has_stats=points is not None, now=now)
        if points is not None and row.live_points != points:
            row.live_points = points
            updated += 1
        if _is_final_game(game) and points is not None and row.final_points != points:
            row.final_points = points
            updated += 1
        if row.scoring_status != next_status:
            row.scoring_status = next_status
            updated += 1
        if next_status == "LIVE":
            live += 1
        if next_status == "FINAL":
            final += 1

    if contest.status in {"LOCKED", "SCORING"} and (live or final):
        contest.status = "SCORING"
    db.flush()
    return {"updated": updated, "live": live, "final": final}


def refresh_open_pick_contests(db: Session) -> dict[str, int]:
    contests = (
        db.query(SaturdayPickContest)
        .filter(SaturdayPickContest.status.in_(("OPEN", "LOCKED", "SCORING")))
        .all()
    )
    totals = {"contests": len(contests), "updated": 0, "live": 0, "final": 0}
    for contest in contests:
        result = refresh_contest_live_scores(db, contest)
        for key in ("updated", "live", "final"):
            totals[key] += result[key]
    db.commit()
    return totals


def _score_featured_player(db: Session, contest: SaturdayPickContest, featured: SaturdayPickPlayer) -> float | None:
    game = db.get(Game, featured.game_id) if featured.game_id else None
    if not _is_final_game(game):
        return None
    return _score_stat(_featured_stat(db, contest, featured), featured.canonical_position)


def finalize_contest(db: Session, contest: SaturdayPickContest) -> SaturdayPickContest:
    if contest.status == "FINAL":
        return contest
    refresh_contest_live_scores(db, contest)
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
        row.live_points = points
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
    if not rows:
        raise ValueError("Saturday Pick 6 contest has no featured players.")
    first_game_player = min(rows, key=lambda row: (as_utc(row.game_time), row.sort_order, row.id))
    player_images = {}
    if settings.player_headshots_enabled:
        player_images = {
            player.id: player.image_url or player.espn_headshot_url
            for player in db.query(Player).filter(Player.id.in_([row.player_id for row in rows] or [-1])).all()
        }
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
        first_game_player=SaturdayPickLockPlayerRead(
            id=first_game_player.id,
            player_id=first_game_player.player_id,
            player_name=first_game_player.player_name_snapshot,
            opponent=first_game_player.opponent_snapshot,
            game_time=first_game_player.game_time,
        ),
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
                image_url=player_images.get(row.player_id),
                projected_points=row.projected_points,
                live_points=row.live_points,
                final_points=row.final_points,
                scoring_status=row.scoring_status,
                sort_order=row.sort_order,
            )
            for row in rows
        ],
        entry=entry_read,
        sponsor=sponsor,
    )
