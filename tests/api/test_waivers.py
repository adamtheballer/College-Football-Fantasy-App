from datetime import datetime, timedelta, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "waiver") -> str:
    email = f"waiver-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={"first_name": f"Waiver{suffix}", "email": email, "password": "StrongPass123!"},
    )
    assert response.status_code == 201
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == email).one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
    return response.json()["access_token"]


def create_league(client, token: str, waiver_type: str = "faab") -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": "Waiver League",
                "season_year": 2026,
                "max_teams": 2,
                "is_private": True,
                "description": None,
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "K": 1, "BENCH": 2},
                "playoff_teams": 2,
                "waiver_type": waiver_type,
                "trade_review_type": "commissioner",
                "superflex_enabled": False,
                "kicker_enabled": True,
                "defense_enabled": False,
            },
            "draft": {
                "draft_datetime_utc": "2026-08-19T18:00:00Z",
                "timezone": "America/Los_Angeles",
                "draft_type": "snake",
                "pick_timer_seconds": 90,
            },
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def create_players_and_roster(db_session, league_id: int) -> tuple[Team, Player, Player]:
    team = db_session.query(Team).filter(Team.league_id == league_id).order_by(Team.id.asc()).first()
    add_player = Player(name="Waiver Add RB", position="RB", school="Texas")
    drop_player = Player(name="Waiver Drop WR", position="WR", school="Oregon")
    db_session.add_all([add_player, drop_player])
    db_session.flush()
    db_session.add(
        RosterEntry(
            league_id=league_id,
            team_id=team.id,
            player_id=drop_player.id,
            slot="WR",
            status="active",
        )
    )
    db_session.commit()
    return team, add_player, drop_player


def test_waiver_claim_submit_list_cancel(client, db_session):
    token = create_user_and_token(client, "submit")
    league = create_league(client, token)
    team, add_player, drop_player = create_players_and_roster(db_session, league["id"])

    submit_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": team.id, "add_player_id": add_player.id, "drop_player_id": drop_player.id, "bid_amount": 7},
        headers=auth_headers(token),
    )
    assert submit_response.status_code == 201
    claim = submit_response.json()
    assert claim["status"] == "pending"
    assert claim["bid_amount"] == 7
    assert claim["priority_at_submission"] == 1

    list_response = client.get(f"/leagues/{league['id']}/waivers/claims", headers=auth_headers(token))
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    tab_response = client.get(f"/leagues/{league['id']}/waivers", headers=auth_headers(token))
    assert tab_response.status_code == 200
    assert tab_response.json()["claims"][0]["id"] == claim["id"]

    cancel_response = client.delete(f"/waivers/claims/{claim['id']}", headers=auth_headers(token))
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"


def test_admin_processes_faab_claims_by_bid_and_records_failure(client, db_session):
    admin_token = create_user_and_token(client, "admin")
    previous_admin_emails = settings.admin_emails
    settings.admin_emails = "waiver-admin@example.com"
    league = create_league(client, admin_token)
    member_token = create_user_and_token(client, f"member-{league['id']}")
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token)).status_code == 200
    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    add_player = Player(name="Shared Waiver RB", position="RB", school="Texas")
    first_drop = Player(name="First Drop WR", position="WR", school="Texas")
    second_drop = Player(name="Second Drop WR", position="WR", school="Oregon")
    db_session.add_all([add_player, first_drop, second_drop])
    db_session.flush()
    db_session.add_all(
        [
            RosterEntry(league_id=league["id"], team_id=teams[0].id, player_id=first_drop.id, slot="WR", status="active"),
            RosterEntry(league_id=league["id"], team_id=teams[1].id, player_id=second_drop.id, slot="WR", status="active"),
        ]
    )
    db_session.commit()

    low_bid = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": teams[0].id, "add_player_id": add_player.id, "drop_player_id": first_drop.id, "bid_amount": 5},
        headers=auth_headers(admin_token),
    )
    high_bid = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": teams[1].id, "add_player_id": add_player.id, "drop_player_id": second_drop.id, "bid_amount": 12},
        headers=auth_headers(member_token),
    )
    assert low_bid.status_code == 201
    assert high_bid.status_code == 201
    db_session.query(WaiverClaim).update({"process_after": datetime.now(timezone.utc) - timedelta(minutes=1)})
    db_session.commit()

    try:
        process_response = client.post(
            "/admin/waivers/process",
            json={"league_id": league["id"]},
            headers=auth_headers(admin_token),
        )
    finally:
        settings.admin_emails = previous_admin_emails

    assert process_response.status_code == 200
    assert process_response.json() == {"processed": 1, "failed": 1, "skipped": 0}
    db_session.expire_all()
    processed = db_session.query(WaiverClaim).filter(WaiverClaim.team_id == teams[1].id).one()
    failed = db_session.query(WaiverClaim).filter(WaiverClaim.team_id == teams[0].id).one()
    assert processed.status == "processed"
    assert failed.status == "failed"
    assert failed.failure_reason == "player is no longer available"
    assert db_session.query(RosterEntry).filter(RosterEntry.team_id == teams[1].id, RosterEntry.player_id == add_player.id).count() == 1
    assert db_session.query(Transaction).filter(Transaction.transaction_type == "waiver_claim").count() == 1
    priority = db_session.query(WaiverPriority).filter(WaiverPriority.team_id == teams[1].id).one()
    assert priority.faab_remaining == 88
    assert (
        db_session.query(NotificationLog)
        .filter(NotificationLog.alert_type.in_(["WAIVER_PROCESSED", "WAIVER_FAILED"]))
        .count()
        == 2
    )


def test_waiver_processing_fails_if_drop_player_changed(client, db_session):
    admin_token = create_user_and_token(client, "dropchanged")
    previous_admin_emails = settings.admin_emails
    settings.admin_emails = "waiver-dropchanged@example.com"
    league = create_league(client, admin_token)
    team, add_player, drop_player = create_players_and_roster(db_session, league["id"])
    claim_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": team.id, "add_player_id": add_player.id, "drop_player_id": drop_player.id, "bid_amount": 3},
        headers=auth_headers(admin_token),
    )
    assert claim_response.status_code == 201
    entry = db_session.query(RosterEntry).filter(RosterEntry.player_id == drop_player.id).one()
    db_session.delete(entry)
    db_session.query(WaiverClaim).update({"process_after": datetime.now(timezone.utc) - timedelta(minutes=1)})
    db_session.commit()

    try:
        process_response = client.post(
            "/admin/waivers/process",
            json={"league_id": league["id"]},
            headers=auth_headers(admin_token),
        )
    finally:
        settings.admin_emails = previous_admin_emails
    assert process_response.status_code == 200
    assert process_response.json()["failed"] == 1
    claim = db_session.get(WaiverClaim, claim_response.json()["id"])
    assert claim.status == "failed"
    assert claim.failure_reason == "drop player is no longer on roster"


def test_waiver_claim_rejects_unavailable_player_and_overspend(client, db_session):
    token = create_user_and_token(client, "reject")
    league = create_league(client, token)
    team, add_player, drop_player = create_players_and_roster(db_session, league["id"])
    db_session.add(
        RosterEntry(
            league_id=league["id"],
            team_id=team.id,
            player_id=add_player.id,
            slot="BENCH",
            status="active",
        )
    )
    db_session.commit()

    unavailable_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": team.id, "add_player_id": add_player.id, "drop_player_id": drop_player.id, "bid_amount": 1},
        headers=auth_headers(token),
    )
    assert unavailable_response.status_code == 409

    db_session.query(RosterEntry).filter(RosterEntry.player_id == add_player.id).delete()
    db_session.commit()
    overspend_response = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": team.id, "add_player_id": add_player.id, "drop_player_id": drop_player.id, "bid_amount": 101},
        headers=auth_headers(token),
    )
    assert overspend_response.status_code == 400
    assert overspend_response.json()["detail"] == "bid exceeds FAAB remaining"
