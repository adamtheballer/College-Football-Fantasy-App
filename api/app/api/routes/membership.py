from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.membership import (
    MembershipRead,
    MembershipUrl,
    ApplePurchaseInput,
    AppleNotificationInput,
    FreeLeagueChoice,
)
from collegefootballfantasy_api.app.services import (
    membership as policy,
    membership_billing as billing,
)
from collegefootballfantasy_api.app.services.auth_security import (
    enforce_auth_rate_limit,
)

router = APIRouter()


def write(db, action):
    try:
        result = action()
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Membership state changed. Refresh and retry."
        ) from exc
    except Exception:
        db.rollback()
        raise


def mutation_user(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enforce_auth_rate_limit(
        db,
        action="membership",
        identifier=str(user.id),
        request=request,
        limit=15,
        window_seconds=60,
    )
    return user


@router.get("", response_model=MembershipRead)
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if policy.rollout_active():

        def ensure_account():
            policy.lock_user(db, user)
            policy.account(db, user)

        write(db, ensure_account)
    return policy.status(db, user)


@router.post("/checkout", response_model=MembershipUrl)
def checkout(db: Session = Depends(get_db), user: User = Depends(mutation_user)):
    return MembershipUrl(url=write(db, lambda: billing.checkout(db, user)))


@router.post("/free-leagues", response_model=MembershipRead)
def free_leagues(
    payload: FreeLeagueChoice,
    db: Session = Depends(get_db),
    user: User = Depends(mutation_user),
):
    write(db, lambda: policy.choose_free_leagues(db, user, payload.league_ids))
    return policy.status(db, user)


@router.post("/portal", response_model=MembershipUrl)
def portal(db: Session = Depends(get_db), user: User = Depends(mutation_user)):
    return MembershipUrl(url=billing.portal(db, user))


@router.post("/sync", response_model=MembershipRead)
def sync(db: Session = Depends(get_db), user: User = Depends(mutation_user)):
    write(db, lambda: billing.sync_customer(db, user))
    return policy.status(db, user)


@router.post("/apple/verify", response_model=MembershipRead)
def verify_apple(
    payload: ApplePurchaseInput,
    db: Session = Depends(get_db),
    user: User = Depends(mutation_user),
):
    write(
        db, lambda: billing.verify_apple_purchase(db, user, payload.signed_transaction)
    )
    return policy.status(db, user)


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    body = await request.body()
    if len(body) > 131072:
        raise HTTPException(413, "Notification is too large.")
    # Run blocking provider I/O outside the event loop.
    from starlette.concurrency import run_in_threadpool

    await run_in_threadpool(
        write, db, lambda: billing.stripe_event(db, body, stripe_signature)
    )
    return {"received": True}


@router.post("/webhooks/apple")
def apple_webhook(payload: AppleNotificationInput, db: Session = Depends(get_db)):
    write(db, lambda: billing.apple_event(db, payload.signedPayload))
    return {"received": True}
