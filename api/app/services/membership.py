"""One entitlement policy shared by billing, API guards and React capabilities."""

from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.membership import (
    MembershipAccount,
    MembershipSubscription,
)
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.membership import MembershipRead


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return (
        value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
    )


def rollout_active(now=None):
    launch = aware(settings.membership_launch_at)
    return bool(
        settings.membership_enabled
        and launch
        and launch.year >= 2027
        and settings.current_season_year >= 2027
        and (now or utcnow()) >= launch
    )


def require_billing_launch():
    if not rollout_active() or not settings.membership_purchases_enabled:
        raise HTTPException(
            409, "Membership purchases open at the configured 2027 season launch."
        )


def lock_user(db, user):
    row = db.scalar(
        select(User)
        .where(User.id == user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(401, "Account is no longer available.")
    return row


def account(db: Session, user: User):
    row = db.get(MembershipAccount, user.id)
    if row is None:
        row = MembershipAccount(user_id=user.id)
        db.add(row)
        db.flush()
    return row


def pro_period(db, user, now=None):
    now = now or utcnow()
    grants = []
    launch = aware(settings.membership_launch_at)
    if launch and launch.year >= 2027 and user.beta_access_granted_at:
        start = max(launch, aware(user.beta_access_granted_at))
        try:
            end = start.replace(year=start.year + 1)
        except ValueError:
            end = start.replace(year=start.year + 1, day=28)
        if start <= now < end:
            grants.append((end, "early_access", False))
    for row in db.scalars(
        select(MembershipSubscription)
        .where(MembershipSubscription.user_id == user.id)
        .execution_options(populate_existing=True)
    ):
        if row.status in {"active", "past_due", "canceled"} and aware(
            row.period_start
        ) <= now < aware(row.period_end):
            grants.append(
                (aware(row.period_end), row.provider, row.cancel_at_period_end)
            )
    return max(
        grants,
        default=(None, None, False),
        key=lambda r: r[0] or datetime.min.replace(tzinfo=timezone.utc),
    )


def league_count(db, user, season=None):
    from collegefootballfantasy_api.app.models.league import League
    from collegefootballfantasy_api.app.models.league_member import LeagueMember
    from collegefootballfantasy_api.app.models.dynasty import (
        DynastyLeague,
        DynastyFranchise,
    )

    season = season or max(settings.current_season_year, 2027)
    regular = (
        db.scalar(
            select(func.count())
            .select_from(LeagueMember)
            .join(League, League.id == LeagueMember.league_id)
            .where(
                LeagueMember.user_id == user.id,
                League.season_year == season,
                League.status != "archived",
            )
        )
        or 0
    )
    dynasty = (
        db.scalar(
            select(func.count())
            .select_from(DynastyFranchise)
            .join(DynastyLeague, DynastyLeague.league_id == DynastyFranchise.league_id)
            .where(
                DynastyFranchise.owner_user_id == user.id,
                DynastyLeague.current_season == season,
            )
        )
        or 0
    )
    return regular + dynasty


def require_feature(db, user, feature, *, season=None):
    if not rollout_active() or (season is not None and season < 2027):
        return
    lock_user(db, user)
    if pro_period(db, user)[0] is None:
        raise HTTPException(
            402, f"Pro membership required for {feature}. Upgrade for $10 USD per year."
        )


def require_league_slot(db, user, *, season):
    if not rollout_active() or season < 2027:
        return
    lock_user(db, user)
    if (
        pro_period(db, user)[0] is None
        and len(regular_memberships(db, user, season)) >= 2
    ):
        raise HTTPException(
            402,
            "The free plan includes two leagues per season. Upgrade to Pro for unlimited leagues.",
        )


def picture_access(db, user):
    if not rollout_active():
        return settings.player_headshots_enabled
    return bool(settings.player_headshots_enabled and user and pro_period(db, user)[0])


def regular_memberships(db, user, season):
    from collegefootballfantasy_api.app.models.league import League
    from collegefootballfantasy_api.app.models.league_member import LeagueMember

    return list(
        db.scalars(
            select(League)
            .join(LeagueMember, LeagueMember.league_id == League.id)
            .where(
                LeagueMember.user_id == user.id,
                League.season_year == season,
                League.status != "archived",
            )
            .order_by(LeagueMember.created_at, League.id)
        )
    )


def free_leagues(db, user, season):
    leagues = regular_memberships(db, user, season)
    row = db.get(MembershipAccount, user.id)
    explicit = row.free_league_ids if row and row.free_league_season == season else []
    valid = [league.id for league in leagues]
    selected = [lid for lid in explicit if lid in valid]
    selected += [lid for lid in valid if lid not in selected][: 2 - len(selected)]
    return [
        dict(id=league.id, name=league.name, selected=league.id in selected)
        for league in leagues
    ]


def choose_free_leagues(db, user, ids):
    if not rollout_active():
        raise HTTPException(
            409, "Free league selection opens at next season's membership launch."
        )
    lock_user(db, user)
    season = settings.current_season_year
    valid = {league.id for league in regular_memberships(db, user, season)}
    if (
        len(set(ids)) != len(ids)
        or not set(ids) <= valid
        or len(ids) != min(2, len(valid))
    ):
        raise HTTPException(422, "Choose up to two of your current regular leagues.")
    row = account(db, user)
    retained = (
        set(row.free_league_ids) & valid if row.free_league_season == season else set()
    )
    if retained and not retained <= set(ids) and pro_period(db, user)[0] is None:
        raise HTTPException(
            409, "Your free leagues are fixed for this season. Pro unlocks all leagues."
        )
    row.free_league_ids, row.free_league_season = ids, season


def require_league_participation(db, user, league_id):
    if not rollout_active() or pro_period(db, user)[0] is not None:
        return
    from collegefootballfantasy_api.app.models.league import League

    league = db.get(League, league_id)
    if league and league.season_year >= 2027:
        selected = {
            item["id"]
            for item in free_leagues(db, user, league.season_year)
            if item["selected"]
        }
        if league_id not in selected:
            raise HTTPException(
                402,
                "This league is read-only on your free plan. Choose two free leagues in Membership or upgrade to Pro.",
            )


def status(db, user, *, include_account=False):
    now = utcnow()
    live = rollout_active(now)
    end, source, cancel = pro_period(db, user, now)
    active = live and end is not None
    row = account(db, user) if include_account else db.get(MembershipAccount, user.id)
    choices = free_leagues(db, user, max(settings.current_season_year, 2027))
    retained = (
        set(row.free_league_ids) & {item["id"] for item in choices} if row else set()
    )
    choice_locked = bool(
        row
        and row.free_league_season == settings.current_season_year
        and retained
        and len(retained) >= min(2, len(choices))
        and not active
    )
    from collegefootballfantasy_api.app.services.membership_billing import (
        stripe_ready,
        apple_ready,
    )

    return MembershipRead(
        plan="pro" if active else "free",
        active=active,
        launch_at=settings.membership_launch_at,
        enforcement_active=live,
        expires_at=end,
        source=source,
        cancel_at_period_end=cancel,
        league_limit=None if active or not live else 2,
        league_count=league_count(db, user),
        free_leagues=choices,
        free_league_choice_locked=choice_locked,
        features={
            "unlimited_leagues": active or not live,
            "dynasty": active or not live,
            "player_pictures": picture_access(db, user),
            "weekly_challenges": active or not live,
            "live_refresh_seconds": 15 if active else 180,
        },
        web_checkout_ready=live
        and settings.membership_purchases_enabled
        and stripe_ready(),
        apple_purchase_ready=live
        and settings.membership_purchases_enabled
        and apple_ready(),
        apple_product_id=settings.appstore_product_id,
        apple_account_token=row.apple_account_token if row else None,
        has_stripe_customer=bool(row and row.stripe_customer_id),
    )
