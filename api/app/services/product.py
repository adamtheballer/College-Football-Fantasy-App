"""First-party participation and actionable Home state; domain ledgers stay authoritative."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from collegefootballfantasy_api.app.models.product_event import ProductEvent
from collegefootballfantasy_api.app.models.challenge_experience import ChallengeAnalyticsPreference
from collegefootballfantasy_api.app.models.weekly_challenge import ChallengeEntry, WeeklyChallenge
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.product import ProductEventCreate, ParticipationMetrics


def utcnow():
    return datetime.now(timezone.utc)


def record_event(db: Session, user: User, payload: ProductEventCreate, *, do_not_track=False) -> bool:
    pref = db.get(ChallengeAnalyticsPreference, user.id)
    if do_not_track or (pref is not None and not pref.enabled):
        return False
    if payload.kind.startswith('challenge_'):
        c = db.get(WeeklyChallenge, payload.challenge_id) if payload.challenge_id else None
        if c is None or c.published_at is None or c.status == 'draft':
            raise HTTPException(404, 'published challenge not found')
        if payload.kind == 'challenge_submit' and not db.scalar(select(ChallengeEntry.id).where(
            ChallengeEntry.user_id == user.id, ChallengeEntry.challenge_id == c.id, ChallengeEntry.status == 'submitted')):
            raise HTTPException(409, 'no submitted entry')
    elif payload.challenge_id is not None:
        raise HTTPException(422, 'challenge_id applies only to challenge events')
    # Daily account/kind/challenge buckets bound storage and make retries and
    # duplicate React mounts idempotent across devices. No caller-supplied IDs.
    now = utcnow()
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    key = f'{user.id}:{payload.kind}:{payload.challenge_id or 0}:{now.date()}'
    if db.scalar(select(ProductEvent.id).where(ProductEvent.dedupe_key == key)):
        return False
    # Even unique challenge IDs cannot bypass this hard per-account daily cap.
    if db.scalar(select(func.count()).select_from(ProductEvent).where(ProductEvent.user_id == user.id,
        ProductEvent.at >= now.replace(hour=0, minute=0, second=0, microsecond=0))) >= 100:
        raise HTTPException(429, 'daily analytics limit reached')
    try:
        with db.begin_nested():
            db.add(ProductEvent(dedupe_key=key, user_id=user.id, at=now, **payload.model_dump()))
            db.flush()
    except IntegrityError:
        return False
    db.commit()
    return True


def metrics(db: Session, days: int, include_test_accounts: bool = False) -> ParticipationMetrics:
    from collegefootballfantasy_api.app.models.league_member import LeagueMember
    since = utcnow() - timedelta(days=days)
    real = select(User.id)
    if not include_test_accounts:
        real = real.where(User.is_admin.is_(False), User.is_test_account.is_(False))
    base = (ProductEvent.user_id.in_(real), ProductEvent.at >= since)
    by_kind = dict(db.query(ProductEvent.kind, func.count(func.distinct(ProductEvent.user_id)))
        .filter(*base).group_by(ProductEvent.kind).all())
    returning = select(ProductEvent.user_id).where(*base, ProductEvent.kind == 'session').group_by(ProductEvent.user_id).having(func.count(func.distinct(func.date(ProductEvent.at))) > 1).subquery()
    versions = db.query(ProductEvent.platform, ProductEvent.app_version, ProductEvent.app_build, func.count(func.distinct(ProductEvent.user_id))).filter(
        *base, ProductEvent.kind == 'session', ProductEvent.platform != 'web').group_by(ProductEvent.platform, ProductEvent.app_version, ProductEvent.app_build).all()
    entries = db.query(ChallengeEntry).filter(ChallengeEntry.user_id.in_(real), ChallengeEntry.status == 'submitted', ChallengeEntry.submitted_at >= since)
    return ParticipationMetrics(days=days, accounts=db.query(User).filter(User.id.in_(real), User.created_at >= since).count(),
        new_accounts_in_leagues=db.query(func.count(func.distinct(User.id))).join(LeagueMember,LeagueMember.user_id == User.id).filter(User.id.in_(real),User.created_at >= since).scalar(),
        active_accounts=by_kind.get('session',0), returning_accounts=db.scalar(select(func.count()).select_from(returning)),
        guide_finished_accounts=by_kind.get('guide_complete',0), challenge_viewers=by_kind.get('challenge_view',0), challenge_starters=by_kind.get('challenge_start',0),
        challenge_submitters=entries.with_entities(func.count(func.distinct(ChallengeEntry.user_id))).scalar(), submitted_entries=entries.count(), sharers=by_kind.get('challenge_share',0),
        notification_openers=by_kind.get('notification_open',0),
        review_authorizations=db.query(User).filter(User.id.in_(real), User.review_request_claimed_at >= since).count(),
        review_invocations=db.query(User).filter(User.id.in_(real), User.review_request_invoked_at >= since).count(),
        native_versions={f'{platform} {version or "unknown"} ({build or "unknown"})': count for platform,version,build,count in versions},
        excluded_test_and_admin=not include_test_accounts, events_since=db.query(func.min(ProductEvent.at)).filter(*base).scalar())
