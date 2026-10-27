"""Future-season membership contracts and provider trust boundaries (no real charges)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
import hashlib
import hmac
import json
import time
from uuid import uuid4
import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from conftest import TestingSessionLocal
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import create_access_token
from collegefootballfantasy_api.app.models.membership import (
    MembershipAccount,
    MembershipSubscription,
    MembershipEvent,
)
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.weekly_challenge import (
    ChallengeRound,
    WeeklyChallenge,
    ChallengeEntry,
)
from collegefootballfantasy_api.app.services import (
    membership as policy,
    membership_billing as billing,
)

NOW = datetime(2027, 9, 4, 12, tzinfo=timezone.utc)
LAUNCH = datetime(
    2027, 8, 1, tzinfo=timezone.utc
)  # Synthetic date, not a product launch date.


@pytest.fixture
def members(client, monkeypatch):
    for key, value in dict(
        membership_enabled=True,
        membership_launch_at=LAUNCH,
        membership_purchases_enabled=True,
        current_season_year=2027,
        environment="test",
        stripe_secret_key=SecretStr("sk_test_membership"),
        stripe_webhook_secret=SecretStr("whsec_membership"),
        stripe_annual_price_id="price_annual",
        appstore_product_id="org.cffb.pro.annual",
        appstore_environment="Sandbox",
        appstore_app_id=12345,
    ).items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(settings, "player_headshots_enabled", True)
    monkeypatch.setattr(policy, "utcnow", lambda: NOW)
    monkeypatch.setattr(billing, "utcnow", lambda: NOW)
    with TestingSessionLocal() as db:
        users = [
            User(
                first_name=f"Member {i}",
                email=f"member{i}@example.com",
                password_hash="test",
                api_token=f"member-{i}",
            )
            for i in range(3)
        ]
        db.add_all(users)
        db.flush()
        accounts = [
            MembershipAccount(user_id=u.id, stripe_customer_id=f"cus_{u.id}")
            for u in users
        ]
        db.add_all(accounts)
        player = Player(
            name="Membership Test Player",
            school="Arizona State",
            position="RB",
            image_url="https://example.edu/player.png",
        )
        db.add(player)
        db.commit()
        ids = [u.id for u in users]
        tokens = [a.apple_account_token for a in accounts]
        headers = [
            {
                "Authorization": f"Bearer {create_access_token(user_id=u.id, email=u.email)[0]}"
            }
            for u in users
        ]
        pid = player.id
    return client, ids, tokens, headers, pid


def grant(uid, provider="stripe", **overrides):
    with TestingSessionLocal() as db:
        data = dict(
            user_id=uid,
            provider=provider,
            provider_subscription_id=f"sub_{uid}",
            status="active",
            period_start=NOW - timedelta(days=10),
            period_end=NOW + timedelta(days=350),
            provider_signed_at=NOW,
        )
        data.update(overrides)
        db.add(MembershipSubscription(**data))
        db.commit()


def fake_stripe(monkeypatch, uid):
    sdk = MagicMock()
    sub = {
        "id": f"sub_{uid}",
        "customer": f"cus_{uid}",
        "status": "active",
        "cancel_at_period_end": False,
        "current_period_start": int((NOW - timedelta(days=10)).timestamp()),
        "current_period_end": int((NOW + timedelta(days=350)).timestamp()),
        "items": {"data": [{"quantity": 1, "price": {"id": "price_annual"}}]},
        "latest_invoice": {
            "id": "in_paid",
            "status": "paid",
            "currency": "usd",
            "amount_paid": 1000,
            "payment_intent": {
                "latest_charge": {"id": "ch_paid", "refunded": False, "disputed": False}
            },
        },
    }
    sdk.v1.subscriptions.retrieve.side_effect = lambda *a, **kw: sub
    sdk.v1.subscriptions.list.return_value = {"data": [sub]}
    sdk.v1.prices.retrieve.return_value = {
        "currency": "usd",
        "unit_amount": 1000,
        "active": True,
        "recurring": {"interval": "year", "interval_count": 1},
    }
    sdk.v1.checkout.sessions.create.return_value = {
        "id": "cs_test_own",
        "url": "https://checkout.stripe.com/test",
        "expires_at": int((NOW + timedelta(minutes=30)).timestamp()),
    }
    sdk.v1.checkout.sessions.retrieve.return_value = {
        "status": "open",
        "url": "https://checkout.stripe.com/test",
    }
    sdk.v1.billing_portal.sessions.create.return_value = {
        "url": "https://billing.stripe.com/test"
    }
    monkeypatch.setattr(billing, "client", lambda: sdk)
    return sdk, sub


def stripe_post(
    client,
    uid,
    event_id="evt_membership",
    kind="customer.subscription.updated",
    payload=None,
):
    body = json.dumps(
        {
            "id": event_id,
            "object": "event",
            "type": kind,
            "data": {
                "object": payload
                or {"id": f"sub_{uid}", "object": "subscription", "status": "active"}
            },
        }
    ).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(
        b"whsec_membership", timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return client.post(
        "/membership/webhooks/stripe",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": f"t={timestamp},v1={signature}",
        },
    )


def apple_tx(token, **changes):
    data = dict(
        productId="org.cffb.pro.annual",
        appAccountToken=token,
        originalTransactionId="original_1",
        transactionId="transaction_1",
        signedDate=int(NOW.timestamp() * 1000),
        purchaseDate=int((NOW - timedelta(days=1)).timestamp() * 1000),
        expiresDate=int((NOW + timedelta(days=364)).timestamp() * 1000),
        revocationDate=None,
        isUpgraded=False,
        currency="USD",
        price=10000,
    )
    data.update(changes)
    return SimpleNamespace(**data)


def test_future_launch_preserves_2026_and_blocks_early_charges(members, monkeypatch):
    client, ids, _, headers, _ = members
    grant(ids[0])
    monkeypatch.setattr(settings, "current_season_year", 2026)
    state = client.get("/membership", headers=headers[0]).json()
    assert not state["enforcement_active"] and not state["active"]
    assert state["features"]["weekly_challenges"] and state["league_limit"] is None
    assert client.post("/membership/checkout", headers=headers[0]).status_code == 409
    monkeypatch.setattr(settings, "current_season_year", 2027)
    monkeypatch.setattr(
        policy, "utcnow", lambda: datetime(2027, 7, 1, tzinfo=timezone.utc)
    )
    assert client.post("/membership/checkout", headers=headers[0]).status_code == 409
    assert client.get("/membership").status_code == 401


def test_paid_expiry_and_early_access_year(members):
    client, ids, _, headers, _ = members
    free = client.get("/membership", headers=headers[0]).json()
    assert free["league_limit"] == 2 and not free["features"]["weekly_challenges"]
    grant(ids[0], cancel_at_period_end=True)
    paid = client.get("/membership", headers=headers[0]).json()
    assert (
        paid["active"]
        and paid["features"]["live_refresh_seconds"] == 15
        and paid["league_limit"] is None
    )
    assert paid["cancel_at_period_end"]
    with TestingSessionLocal() as db:
        row = db.scalar(select(MembershipSubscription))
        row.period_end = NOW - timedelta(days=1)
        db.get(User, ids[1]).beta_access_granted_at = datetime(
            2026, 10, 1, tzinfo=timezone.utc
        )
        db.commit()
    assert not client.get("/membership", headers=headers[0]).json()["active"]
    early = client.get("/membership", headers=headers[1]).json()
    assert early["active"] and early["source"] == "early_access"
    assert early["expires_at"].startswith("2028-08-01")


def test_checkout_uses_server_price_own_account_and_reuses_pending_session(
    members, monkeypatch
):
    client, ids, _, headers, _ = members
    sdk, _ = fake_stripe(monkeypatch, ids[0])
    sdk.v1.subscriptions.list.return_value = {"data": []}
    assert (
        client.post(
            "/membership/checkout",
            headers=headers[0],
            json={"price": "cheap", "user_id": ids[1]},
        ).status_code
        == 200
    )
    assert client.post("/membership/checkout", headers=headers[0]).status_code == 200
    assert sdk.v1.checkout.sessions.create.call_count == 1
    payload = sdk.v1.checkout.sessions.create.call_args.args[0]
    assert payload["customer"] == f"cus_{ids[0]}"
    assert payload["line_items"] == [{"price": "price_annual", "quantity": 1}]
    assert not client.get("/membership", headers=headers[0]).json()["active"]
    sdk.v1.prices.retrieve.return_value["unit_amount"] = 1
    assert client.post("/membership/checkout", headers=headers[1]).status_code == 503


def test_stripe_dispute_loss_revokes_and_won_case_restores_paid_period(
    members, monkeypatch
):
    client, ids, _, headers, _ = members
    sdk, sub = fake_stripe(monkeypatch, ids[0])
    sub["latest_invoice"]["payment_intent"]["latest_charge"]["disputed"] = True
    sdk.v1.disputes.list.return_value = {
        "data": [{"id": "dp_1", "status": "needs_response"}]
    }
    sdk.v1.charges.retrieve.return_value = {"id": "ch_paid", "invoice": "in_paid"}
    sdk.v1.invoices.retrieve.return_value = {"subscription": f"sub_{ids[0]}"}
    payload = {"id": "dp_1", "charge": "ch_paid"}
    assert (
        stripe_post(
            client, ids[0], "evt_disputed", "charge.dispute.created", payload
        ).status_code
        == 200
    )
    assert not client.get("/membership", headers=headers[0]).json()["active"]
    sdk.v1.disputes.list.return_value = {"data": [{"id": "dp_1", "status": "won"}]}
    assert (
        stripe_post(
            client, ids[0], "evt_dispute_won", "charge.dispute.closed", payload
        ).status_code
        == 200
    )
    assert client.get("/membership", headers=headers[0]).json()["active"]
    sdk.v1.disputes.list.assert_called_with({"charge": "ch_paid", "limit": 100})


def test_signed_stripe_webhook_dedup_refund_and_reordered_events(members, monkeypatch):
    client, ids, _, headers, _ = members
    sdk, sub = fake_stripe(monkeypatch, ids[0])
    assert stripe_post(client, ids[0]).status_code == 200
    assert client.get("/membership", headers=headers[0]).json()["active"]
    calls = sdk.v1.subscriptions.retrieve.call_count
    assert stripe_post(client, ids[0]).status_code == 200
    assert sdk.v1.subscriptions.retrieve.call_count == calls
    sub["latest_invoice"]["payment_intent"]["latest_charge"]["refunded"] = True
    assert stripe_post(client, ids[0], "evt_refunded").status_code == 200
    assert not client.get("/membership", headers=headers[0]).json()["active"]
    # An old event claiming active cannot override current provider refund authority.
    assert stripe_post(client, ids[0], "evt_old_active").status_code == 200
    assert not client.get("/membership", headers=headers[0]).json()["active"]
    with TestingSessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(MembershipSubscription)) == 1
        assert db.scalar(select(func.count()).select_from(MembershipEvent)) == 3


def test_invalid_webhook_and_unpaid_invoice_never_grant(members, monkeypatch):
    client, ids, _, headers, _ = members
    sdk, sub = fake_stripe(monkeypatch, ids[0])
    assert (
        client.post(
            "/membership/webhooks/stripe",
            content=b"{}",
            headers={"Stripe-Signature": "t=1,v1=fake"},
        ).status_code
        == 400
    )
    sub["latest_invoice"].update(status="open", amount_paid=0)
    assert stripe_post(client, ids[0]).status_code == 200
    assert not client.get("/membership", headers=headers[0]).json()["active"]
    # Provider failures preserve the previous verified paid period.
    grant(ids[1])
    from stripe import APIConnectionError

    sdk.v1.subscriptions.list.side_effect = APIConnectionError("provider offline")
    assert client.post("/membership/sync", headers=headers[1]).status_code == 503
    assert client.get("/membership", headers=headers[1]).json()["active"]


def test_cancel_at_end_preserves_paid_access_but_immediate_end_revokes(
    members, monkeypatch
):
    client, ids, _, headers, _ = members
    _, sub = fake_stripe(monkeypatch, ids[0])
    sub["cancel_at_period_end"] = True
    assert stripe_post(client, ids[0]).status_code == 200
    assert client.get("/membership", headers=headers[0]).json()["active"]
    sub.update(
        status="canceled", ended_at=int((NOW - timedelta(seconds=1)).timestamp())
    )
    assert stripe_post(client, ids[0], "evt_cancelled").status_code == 200
    assert not client.get("/membership", headers=headers[0]).json()["active"]


def test_apple_verification_account_binding_refund_and_stale_replay(
    members, monkeypatch
):
    client, ids, tokens, headers, _ = members
    tx = apple_tx(tokens[0])
    verifier = MagicMock()
    verifier.verify_and_decode_signed_transaction.side_effect = lambda _: tx
    monkeypatch.setattr(billing, "apple_verifier", lambda: verifier)
    payload = {
        "signed_transaction": "signed-fixture-transaction-verified-by-provider-boundary"
    }
    assert (
        client.post(
            "/membership/apple/verify", headers=headers[1], json=payload
        ).status_code
        == 409
    )
    assert client.post(
        "/membership/apple/verify", headers=headers[0], json=payload
    ).json()["active"]
    original_signed = tx.signedDate
    tx.signedDate += 1000
    tx.revocationDate = tx.signedDate
    assert not client.post(
        "/membership/apple/verify", headers=headers[0], json=payload
    ).json()["active"]
    tx.signedDate = original_signed
    tx.revocationDate = None
    assert not client.post(
        "/membership/apple/verify", headers=headers[0], json=payload
    ).json()["active"]


def test_apple_wrong_sku_invalid_signature_and_production_sandbox_guard(
    members, monkeypatch
):
    client, ids, tokens, headers, _ = members
    invalid = client.post(
        "/membership/apple/verify",
        headers=headers[0],
        json={"signed_transaction": "invalid.signature.without.an.apple.certificate"},
    )
    assert invalid.status_code == 400
    verifier = MagicMock()
    verifier.verify_and_decode_signed_transaction.return_value = apple_tx(
        tokens[0], productId="other.product"
    )
    monkeypatch.setattr(billing, "apple_verifier", lambda: verifier)
    assert (
        client.post(
            "/membership/apple/verify",
            headers=headers[0],
            json={"signed_transaction": "provider-signed-transaction-fixture"},
        ).status_code
        == 400
    )
    monkeypatch.setattr(settings, "environment", "production")
    assert not billing.apple_ready() and not billing.stripe_ready()


def test_third_league_enrollment_and_dynasty_are_server_gated(members):
    client, ids, _, headers, _ = members
    with TestingSessionLocal() as db:
        leagues = [
            League(
                name=f"League {i}",
                platform="custom",
                season_year=2027,
                commissioner_user_id=ids[2],
                max_teams=4,
                status="pre_draft",
            )
            for i in range(3)
        ]
        db.add_all(leagues)
        db.flush()
        for league in leagues[:2]:
            db.add(LeagueMember(league_id=league.id, user_id=ids[0], role="member"))
        db.commit()
        third = leagues[2].id
        with pytest.raises(Exception) as error:
            policy.require_league_slot(db, db.get(User, ids[0]), season=2027)
        assert error.value.status_code == 402
    assert client.post(f"/leagues/{third}/join", headers=headers[0]).status_code == 402
    assert (
        client.post(
            "/dynasty/leagues",
            headers=headers[0],
            json=dict(
                name="Paid dynasty",
                season=2027,
                team_count=2,
                roster_limit=8,
                startup_rounds=2,
                freshman_rounds=1,
            ),
        ).status_code
        == 404
    )  # Preview off by default.


@pytest.mark.parametrize("kind", ["lock", "fanwars", "duels", "creator", "survivor"])
def test_all_weekly_entry_paths_are_paid_but_existing_entries_remain_readable(
    members, kind
):
    client, ids, _, headers, _ = members
    with TestingSessionLocal() as db:
        r = ChallengeRound(
            season=2027, week=1, next_rollover_at=NOW + timedelta(days=7)
        )
        db.add(r)
        db.flush()
        c = WeeklyChallenge(
            round_id=r.id,
            kind=kind,
            status="open",
            published_at=NOW - timedelta(days=1),
            lock_at=NOW + timedelta(days=1),
        )
        db.add(c)
        db.flush()
        db.add(
            ChallengeEntry(
                challenge_id=c.id,
                user_id=ids[0],
                status="submitted",
                revision=1,
                selections=[],
            )
        )
        db.commit()
        cid = c.id
    assert (
        client.put(
            f"/weekly-challenges/challenges/{cid}/entry",
            headers=headers[0],
            json={"expected_revision": 1, "selections": [], "submit": False},
        ).status_code
        == 402
    )
    assert (
        client.get(
            f"/weekly-challenges/challenges/{cid}/entry", headers=headers[0]
        ).status_code
        == 200
    )


def test_player_picture_policy_covers_free_paid_and_anonymous_requests(members):
    client, ids, _, headers, pid = members
    grant(ids[1])
    for auth, expected in [
        ({}, None),
        (headers[0], None),
        (headers[1], "https://example.edu/player.png"),
    ]:
        result = client.get(f"/players/{pid}", headers=auth)
        assert result.status_code == 200, result.text
        assert result.json()["image_url"] == expected
        assert "no-store" in result.headers["cache-control"]
    from collegefootballfantasy_api.app.schemas.weekly_challenge import PoolPlayer
    from collegefootballfantasy_api.app.core.player_picture_access import (
        picture_permission,
    )

    token = picture_permission.set(False)
    try:
        # Alternate snapshots use the same server permission, not just the main player endpoint.
        from collegefootballfantasy_api.app.schemas.trade import TradeOfferItemRead

        assert (
            TradeOfferItemRead(
                id=1,
                trade_offer_id=1,
                team_id=1,
                player_id=pid,
                draft_pick_id=None,
                item_type="player",
                player_image_url="https://example.edu/player.png",
            ).model_dump()["player_image_url"]
            is None
        )
        assert (
            PoolPlayer(
                id=pid,
                game_id=1,
                name="Test",
                school="ASU",
                position="RB",
                image_url="https://example.edu/player.png",
            ).model_dump()["image_url"]
            is None
        )
    finally:
        picture_permission.reset(token)


def test_expired_pro_can_choose_only_two_free_leagues_and_cannot_rotate(members):
    client, ids, _, headers, _ = members
    with TestingSessionLocal() as db:
        leagues = [
            League(
                name=f"Existing {i}",
                platform="custom",
                season_year=2027,
                commissioner_user_id=ids[0],
                max_teams=4,
                status="pre_draft",
            )
            for i in range(3)
        ]
        db.add_all(leagues)
        db.flush()
        from collegefootballfantasy_api.app.models.draft import Draft
        from collegefootballfantasy_api.app.models.league_settings import LeagueSettings

        for league in leagues:
            db.add(
                LeagueMember(league_id=league.id, user_id=ids[0], role="commissioner")
            )
            db.add(
                Draft(league_id=league.id, draft_datetime_utc=NOW + timedelta(days=1))
            )
            db.add(LeagueSettings(league_id=league.id))
        db.commit()
        lids = [league.id for league in leagues]
    state = client.get("/membership", headers=headers[0]).json()
    assert [l["id"] for l in state["free_leagues"] if l["selected"]] == lids[:2]
    assert (
        client.get(f"/leagues/{lids[2]}/members", headers=headers[0]).status_code == 200
    )
    assert (
        client.post(f"/leagues/{lids[2]}/invite/rotate", headers=headers[0]).status_code
        == 402
    )
    chosen = client.post(
        "/membership/free-leagues", headers=headers[0], json={"league_ids": lids[1:]}
    )
    assert chosen.status_code == 200 and chosen.json()["free_league_choice_locked"]
    assert (
        client.post(f"/leagues/{lids[2]}/invite/rotate", headers=headers[0]).status_code
        == 200
    )
    assert (
        client.post(f"/leagues/{lids[0]}/invite/rotate", headers=headers[0]).status_code
        == 402
    )
    assert (
        client.post(
            "/membership/free-leagues",
            headers=headers[0],
            json={"league_ids": lids[:2]},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/membership/free-leagues",
            headers=headers[1],
            json={"league_ids": lids[:2]},
        ).status_code
        == 422
    )
    # Automated processing and ordinary reads use the existing membership authorization without a manual actor.
    from collegefootballfantasy_api.app.api.deps import require_league_member

    with TestingSessionLocal() as db:
        assert require_league_member(db, lids[0], db.get(User, ids[0]))
    grant(ids[0])
    assert (
        client.post(f"/leagues/{lids[0]}/invite/rotate", headers=headers[0]).status_code
        == 200
    )


def test_checkout_reconciles_missing_webhook_before_creating_duplicate(
    members, monkeypatch
):
    client, ids, _, headers, _ = members
    sdk, _ = fake_stripe(monkeypatch, ids[0])
    assert client.post("/membership/checkout", headers=headers[0]).status_code == 409
    sdk.v1.checkout.sessions.create.assert_not_called()
    assert client.post("/membership/sync", headers=headers[0]).json()["active"]


def test_apple_notifications_renewal_refund_and_old_period(members, monkeypatch):
    client, ids, tokens, headers, _ = members
    from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
    from unittest.mock import create_autospec

    verifier = create_autospec(SignedDataVerifier, instance=True)
    tx = apple_tx(tokens[0])
    verifier.verify_and_decode_signed_transaction.return_value = tx
    note = SimpleNamespace(
        notificationUUID="apple_note_1",
        notificationType="DID_RENEW",
        signedDate=tx.signedDate,
        data=SimpleNamespace(
            signedTransactionInfo="verified_tx", signedRenewalInfo="verified_renewal"
        ),
    )
    verifier.verify_and_decode_notification.return_value = note
    verifier.verify_and_decode_renewal_info.return_value = SimpleNamespace(
        originalTransactionId=tx.originalTransactionId,
        productId=tx.productId,
        autoRenewStatus=0,
    )
    monkeypatch.setattr(billing, "apple_verifier", lambda: verifier)
    post = lambda: client.post(
        "/membership/webhooks/apple",
        json={"signedPayload": "verified-notification-fixture"},
    )
    assert post().status_code == 200
    state = client.get("/membership", headers=headers[0]).json()
    assert state["active"] and state["cancel_at_period_end"]
    assert post().status_code == 200
    # A later-delivered refund for last year's transaction must not revoke the current year.
    verifier.verify_and_decode_signed_transaction.return_value = apple_tx(
        tokens[0],
        transactionId="old_transaction",
        purchaseDate=int((NOW - timedelta(days=366)).timestamp() * 1000),
        expiresDate=int((NOW - timedelta(days=1)).timestamp() * 1000),
        revocationDate=tx.signedDate,
    )
    note.notificationUUID = "apple_old_refund"
    note.notificationType = "REFUND"
    note.signedDate += 1000
    assert post().status_code == 200
    assert client.get("/membership", headers=headers[0]).json()["active"]
    verifier.verify_and_decode_signed_transaction.return_value = apple_tx(
        tokens[0], revocationDate=tx.signedDate
    )
    note.notificationUUID = "apple_current_refund"
    note.signedDate += 1000
    assert post().status_code == 200
    assert not client.get("/membership", headers=headers[0]).json()["active"]


def test_account_deletion_cancels_web_subscription_and_retains_tombstone(
    members, monkeypatch
):
    client, ids, _, headers, _ = members
    sdk, _ = fake_stripe(monkeypatch, ids[0])
    from collegefootballfantasy_api.app.services.account_deletion import (
        permanently_delete_user_account,
    )

    with TestingSessionLocal() as db:
        permanently_delete_user_account(db, user=db.get(User, ids[0]))
        db.commit()
        assert db.get(User, ids[0]) is None
        assert db.get(MembershipAccount, ids[0]) is None
        assert db.scalar(select(MembershipSubscription)).user_id is None
    sdk.v1.subscriptions.cancel.assert_called_once_with(f"sub_{ids[0]}")
    assert stripe_post(client, ids[0]).status_code == 200


def test_dynasty_requires_pro_after_launch_and_keeps_expired_history(
    members, monkeypatch
):
    client, ids, _, headers, _ = members
    monkeypatch.setattr(settings, "dynasty_preview_enabled", True)
    payload = dict(
        name="Membership Dynasty",
        season=2027,
        team_count=2,
        roster_limit=8,
        startup_rounds=2,
        freshman_rounds=1,
    )
    assert (
        client.post("/dynasty/leagues", headers=headers[0], json=payload).status_code
        == 402
    )
    grant(ids[0])
    response = client.post("/dynasty/leagues", headers=headers[0], json=payload)
    assert response.status_code == 201, response.text
    lid = response.json()["league_id"]
    with TestingSessionLocal() as db:
        db.scalar(select(MembershipSubscription)).status = "refunded"
        db.commit()
    assert client.get(f"/dynasty/leagues/{lid}", headers=headers[0]).status_code == 200
    assert (
        client.post(f"/dynasty/leagues/{lid}/start", headers=headers[0]).status_code
        == 402
    )


def test_saturday_pick_write_requires_pro(members, monkeypatch):
    client, ids, _, headers, pid = members
    monkeypatch.setattr(settings, "saturday_pick_6_enabled", True)
    monkeypatch.setattr(settings, "saturday_pick_6_public_enabled", True)
    from collegefootballfantasy_api.app.models.saturday_pick import (
        SaturdayPickContest,
        SaturdayPickPlayer,
    )

    with TestingSessionLocal() as db:
        contest = SaturdayPickContest(
            season=2027,
            week_number=1,
            contest_position="RB",
            status="OPEN",
            lock_at=NOW + timedelta(days=1),
        )
        db.add(contest)
        db.flush()
        player = SaturdayPickPlayer(
            contest_id=contest.id,
            player_id=pid,
            canonical_position="RB",
            player_name_snapshot="Test",
            school_snapshot="ASU",
            opponent_snapshot="Test opponent",
            game_time=NOW + timedelta(days=1),
            sort_order=1,
        )
        db.add(player)
        db.commit()
        cid, pick = contest.id, player.id
    assert (
        client.put(
            f"/saturday-pick-6/{cid}/entry",
            headers=headers[0],
            json={"selected_pick_player_id": pick},
        ).status_code
        == 402
    )
    grant(ids[0])
    assert (
        client.put(
            f"/saturday-pick-6/{cid}/entry",
            headers=headers[0],
            json={"selected_pick_player_id": pick},
        ).status_code
        == 200
    )


def test_postgres_last_free_slot_is_serialized(members):
    from conftest import engine

    if engine.dialect.name != "postgresql":
        pytest.skip("row-lock invariant requires disposable PostgreSQL")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from collegefootballfantasy_api.app.models.draft import Draft
    from collegefootballfantasy_api.app.models.league_settings import LeagueSettings

    client, ids, _, headers, _ = members
    with TestingSessionLocal() as db:
        leagues = [
            League(
                name=f"Concurrent {i}",
                season_year=2027,
                commissioner_user_id=ids[2],
                max_teams=4,
                status="pre_draft",
                is_private=False,
            )
            for i in range(3)
        ]
        db.add_all(leagues)
        db.flush()
        for league in leagues:
            db.add(
                Draft(league_id=league.id, draft_datetime_utc=NOW + timedelta(days=1))
            )
            db.add(LeagueSettings(league_id=league.id))
        db.add(LeagueMember(league_id=leagues[0].id, user_id=ids[0], role="member"))
        db.commit()
        candidates = [league.id for league in leagues[1:]]
    barrier = Barrier(2)

    def join(lid):
        barrier.wait(timeout=10)
        return client.post(f"/leagues/{lid}/join", headers=headers[0]).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(join, candidates)) == [200, 402]
    with TestingSessionLocal() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(LeagueMember)
                .where(LeagueMember.user_id == ids[0])
            )
            == 2
        )
