"""Verified, position-scoped fantasy ranking read model for the alpha path.

Snapshots are calculated/persisted only by an explicit certified-finalization
operation.  Read helpers here never write, so cards cannot manufacture a rank
from partial or unverified live statistics.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_season_rank import PlayerSeasonRank
from collegefootballfantasy_api.app.models.player_season_context import PlayerSeasonContext
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points, get_scoring_rules


def normalize_fantasy_position(position: str | None) -> str | None:
    normalized = (position or "").strip().upper()
    if normalized in {"QB", "RB", "WR", "TE"}:
        return normalized
    if normalized in {"K", "PK"}:
        return "K"
    return None


@dataclass(frozen=True)
class SeasonRankSnapshot:
    player_id: int
    season: int
    through_week: int
    position: str
    fantasy_points: float
    position_rank: int


def build_verified_season_rank_snapshots(db: Session, *, season: int, through_week: int) -> list[SeasonRankSnapshot]:
    """Produce a deterministic no-write ranking preview from verified final rows."""

    totals: dict[tuple[int, str], float] = {}
    rows = (
        db.query(PlayerStat, Player.position)
        .join(Player, Player.id == PlayerStat.player_id)
        .outerjoin(
            PlayerSeasonContext,
            and_(
                PlayerSeasonContext.player_id == Player.id,
                PlayerSeasonContext.season == season,
            ),
        )
        .filter(
            PlayerStat.season == season,
            PlayerStat.week >= 1,
            PlayerStat.week <= through_week,
            PlayerStat.verified.is_(True),
            or_(PlayerSeasonContext.id.is_(None), PlayerSeasonContext.is_active.is_(True)),
        )
        .all()
    )
    rules = get_scoring_rules()
    for stat, raw_position in rows:
        position = normalize_fantasy_position(raw_position)
        if position is None:
            continue
        key = (stat.player_id, position)
        totals[key] = totals.get(key, 0.0) + calculate_fantasy_points(stat.stats, rules, position=position)

    by_position: dict[str, list[tuple[int, float]]] = {}
    for (player_id, position), total in totals.items():
        by_position.setdefault(position, []).append((player_id, total))

    snapshots: list[SeasonRankSnapshot] = []
    for position, players in by_position.items():
        for rank, (player_id, total) in enumerate(sorted(players, key=lambda item: (-item[1], item[0])), start=1):
            snapshots.append(
                SeasonRankSnapshot(
                    player_id=player_id,
                    season=season,
                    through_week=through_week,
                    position=position,
                    fantasy_points=round(total, 2),
                    position_rank=rank,
                )
            )
    return snapshots


def persist_verified_season_rank_snapshots(
    db: Session,
    *,
    season: int,
    through_week: int,
    published_at: datetime | None = None,
) -> list[PlayerSeasonRank]:
    """Persist one complete, certified positional-rank snapshot.

    This is deliberately a narrow transactional primitive: the caller must
    have already certified every Week ``through_week`` game and must commit
    the surrounding finalization transaction.  It never derives ranks from
    in-progress or unverified evidence.
    """

    snapshots = build_verified_season_rank_snapshots(db, season=season, through_week=through_week)
    timestamp = published_at or datetime.now(timezone.utc)
    existing_rows = (
        db.query(PlayerSeasonRank)
        .filter(
            PlayerSeasonRank.season == season,
            PlayerSeasonRank.through_week == through_week,
        )
        .all()
    )
    by_player_id = {row.player_id: row for row in existing_rows}
    expected_player_ids = {snapshot.player_id for snapshot in snapshots}

    for stale in existing_rows:
        if stale.player_id not in expected_player_ids:
            db.delete(stale)

    persisted: list[PlayerSeasonRank] = []
    for snapshot in snapshots:
        row = by_player_id.get(snapshot.player_id)
        if row is None:
            row = PlayerSeasonRank(
                player_id=snapshot.player_id,
                season=snapshot.season,
                through_week=snapshot.through_week,
                position=snapshot.position,
                fantasy_points=snapshot.fantasy_points,
                position_rank=snapshot.position_rank,
                published_at=timestamp,
            )
            db.add(row)
        else:
            row.position = snapshot.position
            row.fantasy_points = snapshot.fantasy_points
            row.position_rank = snapshot.position_rank
            row.published_at = timestamp
        persisted.append(row)

    db.flush()
    return persisted


def get_latest_player_positional_rank(db: Session, *, player_id: int, season: int) -> PlayerSeasonRank | None:
    return (
        db.query(PlayerSeasonRank)
        .filter(
            PlayerSeasonRank.player_id == player_id,
            PlayerSeasonRank.season == season,
            PlayerSeasonRank.through_week >= 1,
        )
        .order_by(PlayerSeasonRank.through_week.desc(), PlayerSeasonRank.published_at.desc(), PlayerSeasonRank.id.desc())
        .first()
    )
