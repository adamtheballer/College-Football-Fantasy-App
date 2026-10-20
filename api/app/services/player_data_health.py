"""Observe fact gaps without changing scores or inferring that every bench player played."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update, delete, func
from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
from collegefootballfantasy_api.app.services.league_weeks import season_week_one_start, calendar_cfb_week
from collegefootballfantasy_api.app.services.provider_cache import scope_dict_to_key
from sqlalchemy.orm import Session
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.product_event import ProductEvent
from collegefootballfantasy_api.app.models.challenge_experience import ChallengeEvent
from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState
from collegefootballfantasy_api.app.schemas.product import PlayerHealth
from collegefootballfantasy_api.app.services.player_rankings import ranking_rows
from collegefootballfantasy_api.app.services.fantasy_game_selection import fantasy_stat_weeks
from collegefootballfantasy_api.app.services.player_chart_publication import verified_fantasy_week_stats, points_from_verified_stats


def utcnow():
    return datetime.now(timezone.utc)


def player_health(db: Session, season: int) -> PlayerHealth:
    context, rows = ranking_rows(db, season=season)
    pending = {r.id for r in rows if r.status == 'pending'}
    invalid = set()
    gaps = set()
    if context.week and pending:
        players = db.query(Player).filter(Player.id.in_(pending)).all()
        facts = verified_fantasy_week_stats(db, season=season, week=context.week, players=players, final_games_only=True)
        invalid = {p.id for p in players if p.id in facts and points_from_verified_stats(facts[p.id].stats, position=p.position) is None}
        # A weekly verified record provides evidence that a final provider fact
        # may be missing. Players with no participation evidence remain pending.
        source_weeks = fantasy_stat_weeks(db, season=season, week=context.week, player_ids=pending, player_schools={p.id:p.school for p in players})
        evidence = {pid for pid,week in db.query(PlayerStat.player_id,PlayerStat.week).filter(PlayerStat.player_id.in_(pending), PlayerStat.season == season,
            PlayerStat.week.in_(set(source_weeks.values())), PlayerStat.verified.is_(True)) if week == source_weeks.get(pid)}
        gaps = evidence - set(facts)
    now = utcnow()
    latest = db.query(func.max(PlayerAvailabilityEvent.updated_at)).filter(PlayerAvailabilityEvent.season == season, PlayerAvailabilityEvent.reviewed.is_(True)).scalar()
    latest = latest.replace(tzinfo=timezone.utc) if latest and latest.tzinfo is None else latest
    injury_sources = {}
    in_season = season_week_one_start(season) <= now < season_week_one_start(season)+timedelta(weeks=15)
    if in_season:
        current_week = calendar_cfb_week(season)
        keys = {scope_dict_to_key({'season':season,'week':current_week,'conference':c}):c for c in ['SEC','ACC','BIG12','BIG10']}
        states = {s.scope_key:s for s in db.query(ProviderSyncState).filter(ProviderSyncState.provider == 'official_conference_reports',
            ProviderSyncState.feed == 'injuries_week', ProviderSyncState.scope_key.in_(keys))}
        for key, conference in keys.items():
            state = states.get(key)
            checked = state.last_success_at if state else None
            checked = checked.replace(tzinfo=timezone.utc) if checked and checked.tzinfo is None else checked
            injury_sources[conference] = 'unknown' if not state or not checked else 'failed' if state.status == 'failed' else 'stale' if checked < now-timedelta(hours=48) else 'current'
    injury_status = 'offseason' if not in_season else 'stale' if any(v in {'stale','failed'} for v in injury_sources.values()) else 'unknown' if 'unknown' in injury_sources.values() else 'current'
    return PlayerHealth(season=season, week=context.week, checked_at=now, verified_players=context.verified_players,
        awaiting_stats_or_participation=context.pending_players, latest_fact_at=context.updated_at, latest_reviewed_injury_at=latest, injury_feed_status=injury_status, injury_sources=injury_sources,
        invalid_fact_count=len(invalid), feed_gap_count=len(gaps), sample_player_ids=sorted(invalid | gaps)[:20],
        status='attention' if invalid or gaps or injury_status in {'unknown','stale'} else 'healthy' if context.verified_players else 'pending')


def run_due_product_health(db: Session, season: int, now: datetime | None = None) -> dict:
    now = now or utcnow()
    scope = f'season:{season}'
    dialect = db.get_bind().dialect.name
    # Race-safe creation and atomic due claim across concurrent worker instances.
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(ProviderSyncState).values(provider='cffb', feed='product_health', scope_key=scope, status='idle', meta={}, consecutive_failures=0)
        .on_conflict_do_nothing(index_elements=['provider','feed','scope_key']))
    sid = db.scalar(update(ProviderSyncState).where(ProviderSyncState.provider == 'cffb', ProviderSyncState.feed == 'product_health',
        ProviderSyncState.scope_key == scope, (ProviderSyncState.expires_at.is_(None)) | (ProviderSyncState.expires_at <= now))
        .values(expires_at=now+timedelta(hours=1), last_attempted_at=now, status='checking').execution_options(synchronize_session=False).returning(ProviderSyncState.id))
    if sid is None:
        db.commit()
        return {'status':'not_due'}
    # Claim is durable before the bounded scan; a crash retries next hour.
    db.commit()
    try:
        report = player_health(db, season)
        state = db.get(ProviderSyncState, sid)
        state.status = report.status
        state.consecutive_failures = 0
        state.error_message = None
        state.last_success_at = now
        state.meta = report.model_dump(mode='json')
        cutoff = now - timedelta(days=90)
        db.execute(delete(ProductEvent).where(ProductEvent.at < cutoff))
        db.execute(delete(ChallengeEvent).where(ChallengeEvent.at < cutoff))
        db.commit()
        return {'status':report.status, 'week':report.week, 'feed_gaps':report.feed_gap_count, 'invalid_facts':report.invalid_fact_count}
    except Exception:
        db.rollback()
        db.execute(update(ProviderSyncState).where(ProviderSyncState.id == sid).values(
            status='failed', error_message='Player data check failed; inspect lifecycle worker logs.',
            consecutive_failures=ProviderSyncState.consecutive_failures+1))
        db.commit()
        raise
