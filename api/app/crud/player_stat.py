from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.player_stat import PlayerStat


def get_player_stat(db: Session, player_id: int, season: int, week: int) -> PlayerStat | None:
    stmt = select(PlayerStat).where(
        PlayerStat.player_id == player_id,
        PlayerStat.season == season,
        PlayerStat.week == week,
    )
    return db.scalar(stmt)


def upsert_player_stat(
    db: Session,
    player_id: int,
    season: int,
    week: int,
    stats: dict,
    source: str,
) -> PlayerStat:
    existing = get_player_stat(db, player_id, season, week)
    if existing:
        existing.stats = stats
        existing.source = source
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    entry = PlayerStat(player_id=player_id, season=season, week=week, stats=stats, source=source)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
