from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.api.routes import leagues as league_routes
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.roster import RosterEntry


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str) -> tuple[int, str]:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Ops{suffix}",
            "email": f"ops-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return payload["user"]["id"], payload["access_token"]


def create_league(client, token: str) -> dict:
    payload = {
        "basics": {
            "name": "Ops League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": False,
            "description": "Ops testing",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "BENCH": 4, "IR": 1},
            "playoff_teams": 4,
            "waiver_type": "faab",
            "trade_review_type": "commissioner",
            "superflex_enabled": False,
            "kicker_enabled": True,
            "defense_enabled": False,
        },
        "draft": {
            "draft_datetime_utc": "2026-08-19T18:00:00Z",
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }
    response = client.post("/leagues", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()["league"]


def create_player(client, name: str = "Ops RB") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": "RB",
                "school": "Texas",
                "image_url": None,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def force_draft_live(db_session, *, league_id: int) -> None:
    draft_row = db_session.query(Draft).filter(Draft.league_id == league_id).first()
    assert draft_row is not None
    draft_row.status = "live"
    db_session.add(draft_row)
    timer_row = league_routes._get_or_create_draft_timer_state(db_session, draft_row.id)
    assert timer_row is not None
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()


def test_ops_live_and_ready_endpoints(client):
    live = client.get("/ops/live")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"

    ready = client.get("/ops/ready")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["status"] == "ready"
    assert payload["database"] == "ok"
    assert "realtime_relay" in payload
    assert "realtime_connections" in payload


def test_ops_overview_requires_auth(client):
    response = client.get("/ops/overview")
    assert response.status_code == 401


def test_ops_overview_returns_system_metrics(client):
    _user_id, token = create_user_and_token(client, "overview")
    response = client.get("/ops/overview", headers=auth_headers(token))
    assert response.status_code == 200
    payload = response.json()
    assert "jobs" in payload
    assert "fantasy" in payload
    assert "realtime_relay" in payload
    assert "realtime_connections" in payload


def test_ops_draft_integrity_report_and_repair(client, db_session):
    _user_id, token = create_user_and_token(client, "repair")
    league = create_league(client, token)
    player_id = create_player(client, "Ops Repair RB")
    force_draft_live(db_session, league_id=league["id"])

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    assert pick_response.status_code == 201
    room = pick_response.json()
    user_team_id = room["user_team_id"]
    assert user_team_id is not None

    roster_entry = (
        db_session.query(RosterEntry)
        .filter(RosterEntry.league_id == league["id"], RosterEntry.player_id == player_id)
        .first()
    )
    assert roster_entry is not None
    db_session.delete(roster_entry)
    db_session.commit()

    report = client.get(
        f"/ops/leagues/{league['id']}/draft-integrity",
        headers=auth_headers(token),
    )
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["totals"]["missing_from_roster"] == 1

    repair = client.post(
        f"/ops/leagues/{league['id']}/draft-integrity/repair",
        headers=auth_headers(token),
    )
    assert repair.status_code == 200
    repair_payload = repair.json()
    assert repair_payload["created_entries"] == 1

    repaired_roster_entry = (
        db_session.query(RosterEntry)
        .filter(RosterEntry.league_id == league["id"], RosterEntry.player_id == player_id)
        .first()
    )
    assert repaired_roster_entry is not None
    assert repaired_roster_entry.team_id == user_team_id
