from datetime import datetime, timezone

from conftest import TestingSessionLocal
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState
from collegefootballfantasy_api.app.models.scoring_admin_audit import ScoringAdminAudit
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.scoring_service import recalculate_league_week_scores
from tests.api.scoring_helpers import create_scoring_fixture


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str, *, admin: bool = False) -> tuple[str, int]:
    email = f"admin-scoring-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Admin{suffix}",
            "email": email,
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == email).one()
        user.email_verified_at = datetime.now(timezone.utc)
        user.is_admin = admin
        session.commit()
        return response.json()["access_token"], user.id


def test_non_admin_cannot_access_admin_scoring_routes(client):
    token, _user_id = create_user_and_token(client, "non-admin", admin=False)
    routes = [
        ("get", "/admin/scoring/runs", None),
        ("get", "/admin/scoring/provider-health", None),
        ("get", "/admin/scoring/corrections", None),
        ("post", "/admin/scoring/rerun", {"season": 2026, "week": 1, "reason": "blocked non-admin"}),
        (
            "post",
            "/admin/scoring/corrections/preview",
            {"player_id": 1, "season": 2026, "week": 1, "stats": {"PassingYards": 1}, "reason": "blocked non-admin"},
        ),
        (
            "post",
            "/admin/scoring/corrections/apply",
            {"player_id": 1, "season": 2026, "week": 1, "stats": {"PassingYards": 1}, "reason": "blocked non-admin"},
        ),
        (
            "post",
            "/admin/scoring/reconcile/player-week",
            {"player_id": 1, "season": 2026, "week": 1, "reason": "blocked non-admin"},
        ),
        (
            "post",
            "/admin/scoring/reconcile/league-week",
            {"league_id": 1, "season": 2026, "week": 1, "reason": "blocked non-admin"},
        ),
        (
            "post",
            "/admin/scoring/weeks/finalize",
            {"league_id": 1, "season": 2026, "week": 1, "reason": "blocked non-admin"},
        ),
        (
            "post",
            "/admin/scoring/weeks/reopen",
            {"league_id": 1, "season": 2026, "week": 1, "reason": "blocked non-admin"},
        ),
    ]

    for method, path, body in routes:
        if method == "get":
            response = client.get(path, headers=auth_headers(token))
        else:
            response = client.post(path, json=body, headers=auth_headers(token))
        assert response.status_code == 403
        assert response.json()["detail"] == "admin only"


def test_admin_can_view_provider_health_and_failed_runs(client, db_session):
    token, _user_id = create_user_and_token(client, "health", admin=True)
    db_session.add(
        ProviderSyncState(
            provider="sportsdata",
            feed="player_stats",
            scope_key="2026:1",
            status="failed",
            consecutive_failures=2,
            error_message="provider timeout",
        )
    )
    db_session.commit()
    create_scoring_fixture(db_session)

    failed_response = client.post(
        "/admin/scoring/rerun",
        json={"league_id": 99999, "season": 2026, "week": 1, "provider": "admin", "reason": "force a failed run"},
        headers=auth_headers(token),
    )
    assert failed_response.status_code >= 400

    health_response = client.get("/admin/scoring/provider-health", headers=auth_headers(token))
    runs_response = client.get("/admin/scoring/runs?status=failed", headers=auth_headers(token))

    assert health_response.status_code == 200
    assert health_response.json()["failed_scoring_runs"] >= 1
    assert health_response.json()["sync_states"][0]["provider"] == "sportsdata"
    assert runs_response.status_code == 200
    assert runs_response.json()["total"] >= 1
    db_session.expire_all()
    failed_audit = db_session.query(ScoringAdminAudit).filter_by(action="rerun_scoring_failed").one()
    assert failed_audit.reason == "force a failed run"


def test_admin_preview_and_apply_stat_correction_recalculates_and_audits(client, db_session):
    token, admin_user_id = create_user_and_token(client, "correction", admin=True)
    league, home, _away, players, _matchup = create_scoring_fixture(db_session)
    recalculate_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    payload = {
        "player_id": players["qb"].id,
        "season": 2026,
        "week": 1,
        "stats": {"PassingYards": 300, "PassingTouchdowns": 4},
        "reason": "correct provider box score",
    }
    preview_response = client.post(
        "/admin/scoring/corrections/preview",
        json=payload,
        headers=auth_headers(token),
    )
    assert preview_response.status_code == 200
    assert preview_response.json()["affected_league_ids"] == [league.id]
    assert preview_response.json()["projected_scores"][str(league.id)] == 28.0

    apply_response = client.post(
        "/admin/scoring/corrections/apply",
        json=payload,
        headers=auth_headers(token),
    )

    assert apply_response.status_code == 200
    assert apply_response.json()["audit"]["action"] == "apply_stat_correction"
    stat = db_session.query(PlayerStat).filter_by(player_id=players["qb"].id, season=2026, week=1).one()
    assert stat.stats["PassingYards"] == 300
    qb_score = db_session.query(PlayerWeekScore).filter_by(league_id=league.id, player_id=players["qb"].id, season=2026, week=1).one()
    assert qb_score.fantasy_points == 28.0
    audit = db_session.query(ScoringAdminAudit).filter_by(action="apply_stat_correction").one()
    assert audit.actor_user_id == admin_user_id
    assert audit.affected_league_ids == [league.id]

    history_response = client.get("/admin/scoring/corrections", headers=auth_headers(token))
    assert history_response.status_code == 200
    assert history_response.json()[0]["id"] == audit.id


def test_admin_can_reconcile_finalize_and_reopen_week(client, db_session):
    token, _admin_user_id = create_user_and_token(client, "week", admin=True)
    league, _home, _away, _players, matchup = create_scoring_fixture(db_session)

    reconcile_response = client.post(
        "/admin/scoring/reconcile/league-week",
        json={"league_id": league.id, "season": 2026, "week": 1, "reason": "repair league week totals"},
        headers=auth_headers(token),
    )
    assert reconcile_response.status_code == 200
    assert reconcile_response.json()["summary"]["matchups_updated"] == 1

    finalize_response = client.post(
        "/admin/scoring/weeks/finalize",
        json={"league_id": league.id, "season": 2026, "week": 1, "reason": "official final"},
        headers=auth_headers(token),
    )
    assert finalize_response.status_code == 200
    db_session.refresh(matchup)
    assert matchup.status == "final"

    reopen_response = client.post(
        "/admin/scoring/weeks/reopen",
        json={"league_id": league.id, "season": 2026, "week": 1, "reason": "controlled correction window"},
        headers=auth_headers(token),
    )
    assert reopen_response.status_code == 200
    db_session.expire_all()
    refreshed_matchup = db_session.query(Matchup).filter_by(id=matchup.id).one()
    assert refreshed_matchup.status == "live"
    actions = {row.action for row in db_session.query(ScoringAdminAudit).all()}
    assert {"reconcile_league_week", "final_week", "live_week"}.issubset(actions)
