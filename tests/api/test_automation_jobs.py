from datetime import datetime, timezone

from api.app.models.roster import RosterEntry
from api.app.models.scheduled_league_job import ScheduledLeagueJob
from api.app.models.team import Team
from api.app.models.team_week_score import TeamWeekScore
from api.app.models.waiver_claim import WaiverClaim
from api.app.models.weekly_projection import WeeklyProjection
from api.app.models.matchup import Matchup


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str) -> tuple[int, str]:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Auto{suffix}",
            "email": f"auto-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return payload["user"]["id"], payload["access_token"]


def create_league(client, token: str) -> dict:
    payload = {
        "basics": {
            "name": "Automation League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": False,
            "description": "Automation testing",
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


def test_schedule_and_run_waiver_job(client, db_session):
    owner_user_id, owner_token = create_user_and_token(client, "owner-waiver-job")
    member_user_id, member_token = create_user_and_token(client, "member-waiver-job")
    league = create_league(client, owner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    owner_team = next(row for row in teams if row.owner_user_id == owner_user_id)
    member_team = next(row for row in teams if row.owner_user_id == member_user_id)

    players_response = client.post(
        "/players",
        json=[
            {"external_id": None, "name": "Drop A", "position": "RB", "school": "Texas", "image_url": None},
            {"external_id": None, "name": "Drop B", "position": "WR", "school": "USC", "image_url": None},
            {"external_id": None, "name": "Target C", "position": "RB", "school": "LSU", "image_url": None},
        ],
    )
    assert players_response.status_code == 201
    drop_a = players_response.json()[0]["id"]
    drop_b = players_response.json()[1]["id"]
    target_c = players_response.json()[2]["id"]

    add_owner = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": drop_a, "slot": "RB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert add_owner.status_code == 201
    add_member = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": drop_b, "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert add_member.status_code == 201

    owner_claim = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": owner_team.id, "add_player_id": target_c, "drop_player_id": drop_a, "bid_amount": 11},
        headers=auth_headers(owner_token),
    )
    assert owner_claim.status_code == 201
    member_claim = client.post(
        f"/leagues/{league['id']}/waivers/claims",
        json={"team_id": member_team.id, "add_player_id": target_c, "drop_player_id": drop_b, "bid_amount": 23},
        headers=auth_headers(member_token),
    )
    assert member_claim.status_code == 201

    schedule = client.post(
        f"/leagues/{league['id']}/automation/jobs",
        json={
            "job_type": "waiver_process",
            "run_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"batch_key": "auto-waiver-batch"},
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
    body = run_due.json()
    assert body["processed"] >= 1
    assert body["completed"] >= 1

    claims = db_session.query(WaiverClaim).filter(WaiverClaim.league_id == league["id"]).all()
    assert sorted(row.status for row in claims) == ["lost", "won"]


def test_schedule_and_run_week_scoring_job(client, db_session):
    owner_user_id, owner_token = create_user_and_token(client, "owner-score-job")
    member_user_id, member_token = create_user_and_token(client, "member-score-job")
    league = create_league(client, owner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    owner_team = next(row for row in teams if row.owner_user_id == owner_user_id)
    member_team = next(row for row in teams if row.owner_user_id == member_user_id)

    players_response = client.post(
        "/players",
        json=[
            {"external_id": None, "name": "Score Job QB", "position": "QB", "school": "Bama", "image_url": None},
            {"external_id": None, "name": "Score Job WR", "position": "WR", "school": "UGA", "image_url": None},
        ],
    )
    assert players_response.status_code == 201
    qb_id = players_response.json()[0]["id"]
    wr_id = players_response.json()[1]["id"]

    add_owner = client.post(
        f"/teams/{owner_team.id}/roster",
        json={"player_id": qb_id, "slot": "QB", "status": "active"},
        headers=auth_headers(owner_token),
    )
    assert add_owner.status_code == 201
    add_member = client.post(
        f"/teams/{member_team.id}/roster",
        json={"player_id": wr_id, "slot": "WR", "status": "active"},
        headers=auth_headers(member_token),
    )
    assert add_member.status_code == 201

    db_session.add_all(
        [
            WeeklyProjection(player_id=qb_id, season=2026, week=2, fantasy_points=25.5),
            WeeklyProjection(player_id=wr_id, season=2026, week=2, fantasy_points=17.4),
            Matchup(
                league_id=league["id"],
                season=2026,
                week=2,
                home_team_id=owner_team.id,
                away_team_id=member_team.id,
                status="scheduled",
                home_score=0.0,
                away_score=0.0,
            ),
        ]
    )
    db_session.commit()

    schedule = client.post(
        f"/leagues/{league['id']}/automation/jobs",
        json={
            "job_type": "week_scores_recompute",
            "run_at": datetime.now(timezone.utc).isoformat(),
            "payload": {
                "season": 2026,
                "week": 2,
                "source_mode": "projection_only",
                "finalize_matchups": True,
                "finalize_week": True,
                "note": "Nightly scoring",
            },
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
    payload = run_due.json()
    assert payload["processed"] >= 1
    assert payload["completed"] >= 1

    score_rows = (
        db_session.query(TeamWeekScore)
        .filter(TeamWeekScore.league_id == league["id"], TeamWeekScore.season == 2026, TeamWeekScore.week == 2)
        .all()
    )
    assert len(score_rows) == 2

    jobs = db_session.query(ScheduledLeagueJob).filter(ScheduledLeagueJob.league_id == league["id"]).all()
    assert jobs
    assert all(row.status == "completed" for row in jobs)


def test_list_jobs_requires_membership(client):
    owner_id, owner_token = create_user_and_token(client, "owner-list-jobs")
    _outsider_id, outsider_token = create_user_and_token(client, "outsider-list-jobs")
    league = create_league(client, owner_token)

    response = client.get(
        f"/leagues/{league['id']}/automation/jobs",
        headers=auth_headers(outsider_token),
    )
    assert response.status_code == 403


def test_schedule_job_idempotency_key_replays_without_duplicate(client, db_session):
    _owner_user_id, owner_token = create_user_and_token(client, "owner-idem-job")
    league = create_league(client, owner_token)
    headers = auth_headers(owner_token) | {"Idempotency-Key": "job-idem-1"}

    first = client.post(
        f"/leagues/{league['id']}/automation/jobs",
        json={
            "job_type": "waiver_process",
            "run_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"batch_key": "idem-job-batch"},
        },
        headers=headers,
    )
    assert first.status_code == 201
    first_id = first.json()["id"]

    second = client.post(
        f"/leagues/{league['id']}/automation/jobs",
        json={
            "job_type": "waiver_process",
            "run_at": datetime.now(timezone.utc).isoformat(),
            "payload": {"batch_key": "idem-job-batch"},
        },
        headers=headers,
    )
    assert second.status_code == 201
    assert second.json()["id"] == first_id

    rows = db_session.query(ScheduledLeagueJob).filter(ScheduledLeagueJob.league_id == league["id"]).all()
    assert len(rows) == 1
