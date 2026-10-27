"""Official-provider verification. A client redirect or receipt JSON never grants access."""

from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import stripe
from fastapi import HTTPException
from sqlalchemy import select
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.signed_data_verifier import (
    SignedDataVerifier,
    VerificationException,
    VerificationStatus,
)
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.membership import (
    MembershipAccount,
    MembershipSubscription,
    MembershipEvent,
)
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.membership import (
    aware,
    utcnow,
    account,
    lock_user,
    pro_period,
    require_billing_launch,
)

ROOTS = Path(__file__).resolve().parents[1] / "resources" / "apple-roots"
STRIPE_API_VERSION = "2024-06-20"


def stripe_ready():
    key = (
        settings.stripe_secret_key.get_secret_value()
        if settings.stripe_secret_key
        else ""
    )
    return bool(
        key
        and settings.stripe_webhook_secret
        and settings.stripe_annual_price_id
        and (not settings.is_production or key.startswith(("sk_live_", "rk_live_")))
    )


def apple_ready():
    return bool(
        settings.appstore_product_id
        and settings.appstore_bundle_id
        and (settings.appstore_environment != "Production" or settings.appstore_app_id)
        and (
            not settings.is_production or settings.appstore_environment == "Production"
        )
        and (ROOTS / "AppleRootCA-G3.cer").is_file()
    )


def client():
    if not settings.stripe_secret_key or (
        settings.is_production
        and not settings.stripe_secret_key.get_secret_value().startswith(
            ("sk_live_", "rk_live_")
        )
    ):
        raise HTTPException(503, "Web membership billing is not configured.")
    return stripe.StripeClient(
        settings.stripe_secret_key.get_secret_value(),
        stripe_version=STRIPE_API_VERSION,
        max_network_retries=1,
        http_client=stripe.RequestsClient(timeout=10),
    )


def remote(method, *args, **kwargs):
    try:
        result = method(*args, **kwargs)
        return result.to_dict() if hasattr(result, "to_dict") else result
    except stripe.StripeError as exc:
        raise HTTPException(
            503,
            "Billing provider is unavailable. Your existing paid access is unchanged; retry shortly.",
        ) from exc


def identifier(value):
    return value.get("id") if isinstance(value, dict) else value


def checkout(db, user):
    require_billing_launch()
    if not stripe_ready():
        raise HTTPException(503, "Web membership billing is not configured.")
    user = lock_user(db, user)
    if pro_period(db, user)[0]:
        raise HTTPException(
            409, "Pro is already active. Manage your existing membership instead."
        )
    c = client()
    row = account(db, user)
    if row.stripe_customer_id:
        sync_customer(db, user)
        if pro_period(db, user)[0]:
            raise HTTPException(
                409,
                "An existing web membership is active. Refresh membership status before purchasing.",
            )
    price = remote(c.v1.prices.retrieve, settings.stripe_annual_price_id)
    if (
        price.get("currency"),
        price.get("unit_amount"),
        price.get("recurring", {}).get("interval"),
        price.get("recurring", {}).get("interval_count"),
    ) != ("usd", 1000, "year", 1) or not price.get("active"):
        raise HTTPException(
            503, "The annual $10 USD membership price is not configured correctly."
        )
    if row.stripe_customer_id is None:
        customer = remote(
            c.v1.customers.create,
            {"metadata": {"cffb_user_id": str(user.id)}},
            options={"idempotency_key": f"cffb-membership-customer-{user.id}"},
        )
        row.stripe_customer_id = customer["id"]
    # Reuse the single pending purchase; a second browser must not create a second subscription.
    if (
        row.checkout_id
        and row.checkout_expires_at
        and aware(row.checkout_expires_at) > utcnow()
    ):
        prior = remote(c.v1.checkout.sessions.retrieve, row.checkout_id)
        if prior.get("status") == "open" and prior.get("url"):
            return prior["url"]
        if prior.get("subscription"):
            sync_stripe_subscription(
                db, identifier(prior["subscription"]), expected_user=user
            )
            if pro_period(db, user)[0]:
                raise HTTPException(
                    409,
                    "Your membership payment is already received. Refresh membership status.",
                )
    session = remote(
        c.v1.checkout.sessions.create,
        {
            "customer": row.stripe_customer_id,
            "mode": "subscription",
            "line_items": [{"price": settings.stripe_annual_price_id, "quantity": 1}],
            "client_reference_id": str(user.id),
            "success_url": f"{settings.public_web_url or settings.ui_base_url}/membership?checkout=complete",
            "cancel_url": f"{settings.public_web_url or settings.ui_base_url}/membership?checkout=cancelled",
            "expires_at": int((utcnow() + timedelta(minutes=30)).timestamp()),
        },
        options={"idempotency_key": f"cffb-membership-checkout-{user.id}-{uuid4()}"},
    )
    row.checkout_id, row.checkout_url = session["id"], session["url"]
    row.checkout_expires_at = datetime.fromtimestamp(
        session["expires_at"], timezone.utc
    )
    return session["url"]


def portal(db, user):
    row = db.get(MembershipAccount, user.id)
    if not row or not row.stripe_customer_id:
        raise HTTPException(409, "No web membership is linked to this account.")
    return remote(
        client().v1.billing_portal.sessions.create,
        {
            "customer": row.stripe_customer_id,
            "return_url": f"{settings.public_web_url or settings.ui_base_url}/membership",
        },
    )["url"]


def sync_stripe_subscription(db, subscription_id, expected_user=None):
    c = client()
    sub = remote(
        c.v1.subscriptions.retrieve,
        subscription_id,
        {"expand": ["latest_invoice.payment_intent.latest_charge"]},
    )
    owner = db.scalar(
        select(MembershipAccount).where(
            MembershipAccount.stripe_customer_id == identifier(sub.get("customer"))
        )
    )
    if owner is None:
        tombstone = db.scalar(
            select(MembershipSubscription).where(
                MembershipSubscription.provider == "stripe",
                MembershipSubscription.provider_subscription_id == subscription_id,
            )
        )
        if tombstone and tombstone.user_id is None and expected_user is None:
            return None
        # Checkout's account transaction may still be committing. Do not acknowledge a lost grant.
        raise HTTPException(
            503, "Membership account is not ready; retry the notification."
        )
    user = db.get(User, owner.user_id)
    if expected_user and user.id != expected_user.id:
        raise HTTPException(403, "Subscription belongs to another account.")
    lock_user(db, user)
    # Fetch AFTER the account lock too: out-of-order webhooks read today's authority.
    sub = remote(
        c.v1.subscriptions.retrieve,
        subscription_id,
        {"expand": ["latest_invoice.payment_intent.latest_charge"]},
    )
    items = sub.get("items", {}).get("data", [])
    if (
        len(items) != 1
        or identifier(items[0].get("price")) != settings.stripe_annual_price_id
        or items[0].get("quantity") != 1
    ):
        raise HTTPException(400, "Subscription is not the annual Pro product.")
    invoice = sub.get("latest_invoice")
    if not isinstance(invoice, dict):
        raise HTTPException(503, "Payment authority is not available yet.")
    existing = db.scalar(
        select(MembershipSubscription)
        .where(
            MembershipSubscription.provider == "stripe",
            MembershipSubscription.provider_subscription_id == subscription_id,
        )
        .execution_options(populate_existing=True)
    )
    if existing and existing.user_id != user.id:
        raise HTTPException(409, "Subscription ownership cannot be reassigned.")
    start = datetime.fromtimestamp(sub["current_period_start"], timezone.utc)
    end = datetime.fromtimestamp(sub["current_period_end"], timezone.utc)
    paid = (
        invoice.get("status") == "paid"
        and invoice.get("currency") == "usd"
        and invoice.get("amount_paid", 0) >= 1000
    )
    charge = (
        (invoice.get("payment_intent") or {}).get("latest_charge")
        if isinstance(invoice.get("payment_intent"), dict)
        else None
    )
    refunded = bool(isinstance(charge, dict) and charge.get("refunded"))
    disputed = False
    if isinstance(charge, dict) and charge.get("disputed"):
        # Charge exposes `disputed`, not a dispute ID. Query the charge's
        # current disputes so a won/closed case restores a still-paid period.
        cases = remote(c.v1.disputes.list, {"charge": charge["id"], "limit": 100})[
            "data"
        ]
        disputed = not cases or any(
            case.get("status") not in {"won", "warning_closed"} for case in cases
        )
    if existing is None:
        existing = MembershipSubscription(
            user_id=user.id,
            provider="stripe",
            provider_subscription_id=subscription_id,
            period_start=start,
            period_end=start,
            status="incomplete",
            provider_signed_at=utcnow(),
        )
        db.add(existing)
    if paid:
        existing.period_start, existing.period_end = start, end
        existing.transaction_id = invoice["id"]
    if sub.get("ended_at"):
        existing.period_end = min(
            aware(existing.period_end),
            datetime.fromtimestamp(sub["ended_at"], timezone.utc),
        )
    provider_status = sub.get("status")
    existing.status = (
        "refunded"
        if refunded or disputed
        else (
            "canceled"
            if provider_status == "canceled"
            else (
                "active"
                if provider_status == "active" and paid
                else (
                    "past_due"
                    if provider_status == "past_due"
                    else (
                        "expired"
                        if provider_status in {"unpaid", "incomplete_expired", "paused"}
                        else "incomplete"
                    )
                )
            )
        )
    )
    existing.cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
    existing.provider_signed_at = utcnow()
    db.flush()
    return user


def sync_customer(db, user):
    lock_user(db, user)
    row = db.get(MembershipAccount, user.id)
    if not row or not row.stripe_customer_id:
        return
    for sub in customer_subscriptions(client(), row.stripe_customer_id):
        if any(
            identifier(i.get("price")) == settings.stripe_annual_price_id
            for i in sub.get("items", {}).get("data", [])
        ):
            sync_stripe_subscription(db, sub["id"], expected_user=user)


def customer_subscriptions(c, customer_id):
    params = {"customer": customer_id, "status": "all", "limit": 100}
    while True:
        result = remote(c.v1.subscriptions.list, params)
        yield from result["data"]
        if not result.get("has_more") or not result["data"]:
            break
        params = {**params, "starting_after": result["data"][-1]["id"]}


def stripe_event(db, raw_body, signature):
    if not stripe_ready():
        raise HTTPException(503, "Stripe notifications are not configured.")
    try:
        event = stripe.Webhook.construct_event(
            raw_body, signature, settings.stripe_webhook_secret.get_secret_value()
        )
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise HTTPException(400, "Invalid billing notification signature.") from exc
    event_id, kind = event["id"], event["type"]
    if db.scalar(
        select(MembershipEvent.id).where(
            MembershipEvent.provider == "stripe", MembershipEvent.event_id == event_id
        )
    ):
        return
    obj = event["data"]["object"]
    obj = obj.to_dict() if hasattr(obj, "to_dict") else obj
    sid = None
    if kind.startswith("customer.subscription."):
        sid = obj["id"]
    elif kind.startswith("invoice."):
        sid = identifier(obj.get("subscription")) or identifier(
            obj.get("parent", {}).get("subscription_details", {}).get("subscription")
        )
    elif kind == "checkout.session.completed":
        sid = identifier(obj.get("subscription"))
    elif kind in {"charge.refunded", "charge.dispute.created", "charge.dispute.closed"}:
        charge = (
            obj
            if kind == "charge.refunded"
            else remote(client().v1.charges.retrieve, identifier(obj["charge"]))
        )
        if charge.get("invoice"):
            invoice = remote(
                client().v1.invoices.retrieve, identifier(charge["invoice"])
            )
            sid = identifier(invoice.get("subscription"))
    if not sid:
        return
    user = sync_stripe_subscription(db, sid)
    # Same-user concurrent deliveries have serialized by this point.
    if not db.scalar(
        select(MembershipEvent.id).where(
            MembershipEvent.provider == "stripe", MembershipEvent.event_id == event_id
        )
    ):
        db.add(
            MembershipEvent(
                provider="stripe",
                event_id=event_id,
                event_type=kind,
                provider_subscription_id=sid,
                user_id=user.id if user else None,
            )
        )


def apple_verifier():
    if not apple_ready():
        raise HTTPException(503, "App Store membership billing is not configured.")
    return SignedDataVerifier(
        [p.read_bytes() for p in sorted(ROOTS.glob("*.cer"))],
        True,
        Environment(settings.appstore_environment),
        settings.appstore_bundle_id,
        settings.appstore_app_id,
    )


def decode_apple(method, signed):
    try:
        return method(signed)
    except VerificationException as exc:
        code = (
            503
            if exc.status == VerificationStatus.RETRYABLE_VERIFICATION_FAILURE
            else 400
        )
        raise HTTPException(
            code, "App Store purchase could not be verified. No access was changed."
        ) from exc


def milliseconds(value):
    if not isinstance(value, (int, float)) or value <= 0:
        raise HTTPException(
            400, "App Store transaction is missing verified period dates."
        )
    return datetime.fromtimestamp(value / 1000, timezone.utc)


def apply_apple(
    db,
    tx,
    *,
    expected_user=None,
    event_id=None,
    event_type="transaction",
    signed_at=None,
    renewal=None,
):
    if tx.productId != settings.appstore_product_id or not tx.appAccountToken:
        raise HTTPException(
            400, "Purchase is not the configured Pro product with an account binding."
        )
    owner = db.scalar(
        select(MembershipAccount).where(
            MembershipAccount.apple_account_token == str(tx.appAccountToken).lower()
        )
    )
    if owner is None or (expected_user and owner.user_id != expected_user.id):
        deleted = db.scalar(
            select(MembershipSubscription).where(
                MembershipSubscription.provider == "apple",
                MembershipSubscription.provider_subscription_id
                == str(tx.originalTransactionId),
            )
        )
        if expected_user is None and deleted and deleted.user_id is None:
            return None
        raise HTTPException(
            409,
            "Purchase belongs to another app account. Sign in to the original account to restore.",
        )
    user = db.get(User, owner.user_id)
    lock_user(db, user)
    original, transaction = str(tx.originalTransactionId or ""), str(
        tx.transactionId or ""
    )
    if not original or not transaction:
        raise HTTPException(400, "App Store transaction identifiers are missing.")
    signed = milliseconds(signed_at or tx.signedDate)
    start, end = milliseconds(tx.purchaseDate), milliseconds(tx.expiresDate)
    if end < start or signed > utcnow() + timedelta(minutes=5):
        raise HTTPException(400, "App Store transaction dates are invalid.")
    if settings.appstore_environment == "Production" and end - start < timedelta(
        days=350
    ):
        raise HTTPException(400, "Purchase is not an annual membership period.")
    if getattr(
        getattr(tx, "offerDiscountType", None), "value", None
    ) == "FREE_TRIAL" or (
        getattr(tx, "currency", None) == "USD"
        and getattr(tx, "price", 10000) is not None
        and tx.price < 10000
    ):
        raise HTTPException(
            400, "The configured membership does not include unpaid trial access."
        )
    eid = (
        event_id
        or "tx:" + sha256(f"{transaction}:{tx.signedDate}".encode()).hexdigest()
    )
    if db.scalar(
        select(MembershipEvent.id).where(
            MembershipEvent.provider == "apple", MembershipEvent.event_id == eid
        )
    ):
        return user
    row = db.scalar(
        select(MembershipSubscription)
        .where(
            MembershipSubscription.provider == "apple",
            MembershipSubscription.provider_subscription_id == original,
        )
        .execution_options(populate_existing=True)
    )
    if row and row.user_id != user.id:
        raise HTTPException(409, "Subscription ownership cannot be reassigned.")
    if row is None:
        row = MembershipSubscription(
            user_id=user.id,
            provider="apple",
            provider_subscription_id=original,
            status="incomplete",
            period_start=start,
            period_end=end,
            provider_signed_at=signed,
        )
        db.add(row)
    if (
        end >= aware(row.period_end) or transaction == row.transaction_id
    ) and signed >= aware(row.provider_signed_at):
        row.period_start, row.period_end = start, end
        row.transaction_id, row.provider_signed_at = transaction, signed
        row.status = (
            "refunded"
            if getattr(tx, "revocationDate", None) or event_type in {"REFUND", "REVOKE"}
            else "expired" if getattr(tx, "isUpgraded", False) else "active"
        )
        if renewal is not None:
            row.cancel_at_period_end = getattr(renewal, "autoRenewStatus", None) == 0
    db.add(
        MembershipEvent(
            provider="apple",
            event_id=eid,
            event_type=event_type,
            provider_subscription_id=original,
            user_id=user.id,
        )
    )
    db.flush()
    return user


def verify_apple_purchase(db, user, signed):
    tx = decode_apple(apple_verifier().verify_and_decode_signed_transaction, signed)
    return apply_apple(db, tx, expected_user=user)


def apple_event(db, signed):
    verifier = apple_verifier()
    note = decode_apple(verifier.verify_and_decode_notification, signed)
    if not note.data or not note.data.signedTransactionInfo:
        return  # Verified TEST/summary notifications carry no grant.
    tx = decode_apple(
        verifier.verify_and_decode_signed_transaction, note.data.signedTransactionInfo
    )
    renewal = (
        decode_apple(
            verifier.verify_and_decode_renewal_info, note.data.signedRenewalInfo
        )
        if note.data.signedRenewalInfo
        else None
    )
    if renewal and (
        renewal.originalTransactionId != tx.originalTransactionId
        or renewal.productId != tx.productId
    ):
        raise HTTPException(400, "App Store renewal and transaction do not match.")
    kind = getattr(note.notificationType, "value", note.notificationType)
    return apply_apple(
        db,
        tx,
        event_id=str(note.notificationUUID),
        event_type=str(kind),
        signed_at=note.signedDate,
        renewal=renewal,
    )


def cancel_for_account_deletion(db, user):
    # Apple renewal is controlled by the Apple account; the UI explains its Manage link.
    row = db.get(MembershipAccount, user.id)
    if row and row.stripe_customer_id:
        c = client()
        for sub in customer_subscriptions(c, row.stripe_customer_id):
            if any(
                identifier(i.get("price")) == settings.stripe_annual_price_id
                for i in sub.get("items", {}).get("data", [])
            ):
                if sub.get("status") != "canceled":
                    remote(c.v1.subscriptions.cancel, sub["id"])
                existing = db.scalar(
                    select(MembershipSubscription).where(
                        MembershipSubscription.provider == "stripe",
                        MembershipSubscription.provider_subscription_id == sub["id"],
                    )
                )
                if existing is None:
                    # Even a first webhook delivered after deletion must find an
                    # immutable tombstone instead of trying to recreate the owner.
                    db.add(
                        MembershipSubscription(
                            user_id=user.id,
                            provider="stripe",
                            provider_subscription_id=sub["id"],
                            status="canceled",
                            period_start=utcnow(),
                            period_end=utcnow(),
                            provider_signed_at=utcnow(),
                        )
                    )
        db.flush()
