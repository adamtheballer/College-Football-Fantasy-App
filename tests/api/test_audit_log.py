from datetime import datetime, timezone


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str) -> tuple[int, str]:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Audit{suffix}",
            "email": f"audit-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return payload["user"]["id"], payload["access_token"]


def create_league(client, token: str) -> dict:
    payload = {
        "basics": {
            "name": "Audit League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": False,
            "description": "Audit trail testing",
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


def test_audit_log_tracks_commissioner_actions(client):
    _owner_user_id, owner_token = create_user_and_token(client, "owner-actions")
    league = create_league(client, owner_token)

    pause_response = client.post(
        f"/leagues/{league['id']}/draft-room/status",
        json={"status": "paused"},
        headers=auth_headers(owner_token),
    )
    assert pause_response.status_code == 200

    schedule = client.post(
        f"/leagues/{league['id']}/automation/jobs",
        json={
            "job_type": "waiver_process",
            "run_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"batch_key": "audit-batch"},
        },
        headers=auth_headers(owner_token),
    )
    assert schedule.status_code == 201

    run_due = client.post(
        f"/leagues/{league['id']}/automation/jobs/run-due",
        json={"limit": 10},
        headers=auth_headers(owner_token),
    )
    assert run_due.status_code == 200

    audit_response = client.get(
        f"/leagues/{league['id']}/audit-log",
        headers=auth_headers(owner_token),
    )
    assert audit_response.status_code == 200
    data = audit_response.json()["data"]
    action_types = {row["action_type"] for row in data}
    assert "draft.status.changed" in action_types
    assert "automation.job.scheduled" in action_types
    assert "automation.jobs.run_due" in action_types


def test_audit_log_requires_membership(client):
    _owner_user_id, owner_token = create_user_and_token(client, "owner-authz")
    _outsider_user_id, outsider_token = create_user_and_token(client, "outsider-authz")
    league = create_league(client, owner_token)

    response = client.get(
        f"/leagues/{league['id']}/audit-log",
        headers=auth_headers(outsider_token),
    )
    assert response.status_code == 403
