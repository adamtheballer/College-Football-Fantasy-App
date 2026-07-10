from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import create_access_token, generate_token, hash_password
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_provider_id import PlayerProviderId
from collegefootballfantasy_api.app.models.provider_player_identity_audit import ProviderPlayerIdentityAudit
from collegefootballfantasy_api.app.models.provider_sync_job import ProviderSyncJob
from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState
from collegefootballfantasy_api.app.models.provider_unmatched_player_row import ProviderUnmatchedPlayerRow
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.espn_stats_sync import upsert_espn_weekly_player_stats
from collegefootballfantasy_api.app.services.provider_identity_audit import record_unmatched_provider_row
from collegefootballfantasy_api.app.services.provider_stats_service import upsert_sportsdata_weekly_player_stats
from collegefootballfantasy_api.app.services.team_provider_mapping import upsert_team_provider_id
from tests.api.scoring_helpers import create_scoring_fixture
from tests.api.test_espn_boxscores import espn_summary_payload


class FakeESPNClient:
    def __init__(self, payload: dict | None = None):
        self.payload = payload or espn_summary_payload()

    def get_weekly_boxscore_summaries(self, season, week):
        return [self.payload]


class FakeSportsDataClient:
    def get_weekly_player_stats(self, season, week):
        return [
            {"PlayerID": "sd-1", "Name": "Matched RB", "RushingYards": 40},
            {"PlayerID": "sd-missing", "Name": "Missing RB", "RushingYards": 20},
            {"Name": "No ID WR", "ReceivingYards": 10},
        ]


class InvalidSportsDataClient:
    def get_weekly_player_stats(self, season, week):
        return [
            {"PlayerID": "sd-1", "Name": "Matched RB", "RushingYards": 40},
            {"PlayerID": "sd-invalid", "Name": "No Stats"},
        ]


def _auth_headers(user: User) -> dict[str, str]:
    token, _expires_at = create_access_token(user_id=user.id, email=user.email)
    return {"Authorization": f"Bearer {token}"}


def _create_user(db_session, email: str) -> User:
    user = User(
        first_name="Admin",
        email=email,
        username=email.split("@")[0],
        password_hash=hash_password("StrongPass123!"),
        api_token=generate_token(32),
        email_verified_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_espn_sync_records_identity_audits_and_unmatched_rows(client, db_session):
    by_external_id = Player(name="Arch Manning", position="QB", school="Texas", external_id="espn:101")
    by_name_school = Player(name="Ryan Wingo", position="WR", school="Texas", external_id="sportsdata:202")
    db_session.add_all([by_external_id, by_name_school])
    db_session.commit()

    result = upsert_espn_weekly_player_stats(db_session, season=2026, week=1, client=FakeESPNClient())

    assert result["rows_seen"] == 3
    assert result["upserted"] == 2
    assert result["skipped"] == 1

    audits = db_session.query(ProviderPlayerIdentityAudit).order_by(ProviderPlayerIdentityAudit.id.asc()).all()
    assert [(row.provider_player_name, row.match_type) for row in audits] == [
        ("Arch Manning", "external_id"),
        ("Ryan Wingo", "name_school"),
    ]

    unmatched = db_session.query(ProviderUnmatchedPlayerRow).one()
    assert unmatched.provider == "espn"
    assert unmatched.provider_player_name == "Bert Auburn"
    assert unmatched.reason == "no local player matched provider row"


def test_espn_sync_matches_provider_id_table_when_legacy_external_id_is_sportsdata(client, db_session):
    player = Player(name="Arch Manning", position="QB", school="Texas", external_id="sd-101")
    db_session.add(player)
    db_session.flush()
    db_session.add(
        PlayerProviderId(
            player_id=player.id,
            provider="espn",
            provider_player_id="101",
            provider_team_id="Texas",
            match_confidence=100,
        )
    )
    db_session.commit()

    result = upsert_espn_weekly_player_stats(db_session, season=2026, week=1, client=FakeESPNClient())

    assert result["upserted"] == 1
    audit = db_session.query(ProviderPlayerIdentityAudit).one()
    assert audit.player_id == player.id
    assert audit.match_type == "external_id"


def test_espn_sync_does_not_guess_duplicate_name_school_match(client, db_session):
    db_session.add_all(
        [
            Player(name="Ryan Wingo", position="WR", school="Texas", external_id="sportsdata:202-a"),
            Player(name="Ryan Wingo", position="WR", school="Texas", external_id="sportsdata:202-b"),
        ]
    )
    db_session.commit()

    result = upsert_espn_weekly_player_stats(db_session, season=2026, week=1, client=FakeESPNClient())

    assert result["rows_seen"] == 3
    assert result["upserted"] == 0
    assert result["skipped"] == 3
    reasons = {row.provider_player_name: row.reason for row in db_session.query(ProviderUnmatchedPlayerRow).all()}
    assert reasons["Ryan Wingo"] == "duplicate local players share provider name and school"


def test_sportsdata_provider_adapter_records_unmatched_rows(client, db_session):
    matched = Player(name="Matched RB", position="RB", school="Texas", external_id="sd-1")
    db_session.add(matched)
    db_session.commit()

    result = upsert_sportsdata_weekly_player_stats(
        db_session,
        season=2026,
        week=1,
        client=FakeSportsDataClient(),
    )

    assert result["events"] == 0
    assert result["rows_seen"] == 3
    assert result["upserted"] == 1
    assert result["skipped"] == 2
    assert result["rows_inserted"] == 1
    assert result["rows_updated"] == 0
    assert result["rows_rejected"] == 2
    assert result["provider_sync_job_id"]
    job = db_session.get(ProviderSyncJob, result["provider_sync_job_id"])
    assert job is not None
    assert job.provider == "sportsdata"
    assert job.feed == "player_game_stats_week"
    assert job.rows_seen == 3
    assert job.rows_inserted == 1
    assert job.rows_rejected == 2
    unmatched = db_session.query(ProviderUnmatchedPlayerRow).order_by(ProviderUnmatchedPlayerRow.id.asc()).all()
    assert unmatched[0].reason == "no local player matched provider row"
    assert unmatched[1].reason.startswith("invalid provider payload:")


def test_sportsdata_provider_adapter_matches_provider_id_table_when_legacy_external_id_is_espn(client, db_session):
    matched = Player(name="Matched RB", position="RB", school="Texas", external_id="espn:999")
    db_session.add(matched)
    db_session.flush()
    db_session.add(
        PlayerProviderId(
            player_id=matched.id,
            provider="sportsdata",
            provider_player_id="sd-1",
            provider_team_id="Texas",
            match_confidence=100,
        )
    )
    db_session.commit()

    result = upsert_sportsdata_weekly_player_stats(
        db_session,
        season=2026,
        week=1,
        client=FakeSportsDataClient(),
    )

    assert result["upserted"] == 1
    assert result["skipped"] == 2


def test_sportsdata_invalid_provider_rows_are_quarantined(client, db_session):
    matched = Player(name="Matched RB", position="RB", school="Texas", external_id="sd-1")
    db_session.add(matched)
    db_session.commit()

    result = upsert_sportsdata_weekly_player_stats(
        db_session,
        season=2026,
        week=1,
        client=InvalidSportsDataClient(),
    )

    assert result["rows_seen"] == 2
    assert result["upserted"] == 1
    assert result["rows_rejected"] == 1
    unmatched = db_session.query(ProviderUnmatchedPlayerRow).filter_by(provider="sportsdata").one()
    assert unmatched.reason.startswith("invalid provider payload:")


def test_unmatched_provider_rows_are_deduped_by_identity(client, db_session):
    first = record_unmatched_provider_row(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        row={"ESPNPlayerID": "777", "PlayerName": "Missing QB", "School": "Texas", "PassingYards": 200},
        reason="no local player matched provider row",
    )
    db_session.flush()
    second = record_unmatched_provider_row(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        row={"ESPNPlayerID": "777", "PlayerName": "Missing QB", "School": "Texas", "PassingYards": 250},
        reason="no local player matched provider row",
    )
    db_session.commit()

    rows = db_session.query(ProviderUnmatchedPlayerRow).all()
    assert len(rows) == 1
    assert first.id == second.id
    assert rows[0].dedupe_hash
    assert rows[0].raw_json["PassingYards"] == 250


def test_admin_can_map_unmatched_provider_row_to_player(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    player = Player(name="Mapped QB", position="QB", school="Texas")
    db_session.add(player)
    db_session.flush()
    unmatched = record_unmatched_provider_row(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        row={"ESPNPlayerID": "888", "PlayerName": "Mapped QB", "School": "Texas"},
        reason="no local player matched provider row",
    )
    db_session.commit()

    response = client.post(
        f"/admin/scoring/unmatched-provider-rows/{unmatched.id}/map",
        json={"player_id": player.id, "match_confidence": 95},
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "mapped"
    assert payload["mapped_player_id"] == player.id
    provider_id = db_session.query(PlayerProviderId).filter_by(player_id=player.id, provider="espn").one()
    assert provider_id.provider_player_id == "888"
    assert provider_id.match_confidence == 95
    assert provider_id.verified_by_user_id == admin.id
    db_session.expire_all()
    refreshed_unmatched = db_session.get(ProviderUnmatchedPlayerRow, unmatched.id)
    assert refreshed_unmatched.status == "mapped"
    assert refreshed_unmatched.resolved_by_user_id == admin.id
    assert refreshed_unmatched.resolved_at is not None


def test_admin_map_unmatched_provider_row_rejects_invalid_schema(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    unmatched = record_unmatched_provider_row(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        row={"ESPNPlayerID": "999", "PlayerName": "Bad Schema QB", "School": "Texas"},
        reason="no local player matched provider row",
    )
    db_session.commit()

    response = client.post(
        f"/admin/scoring/unmatched-provider-rows/{unmatched.id}/map",
        json={"player_id": "not-an-int", "match_confidence": 95, "unexpected": True},
        headers=_auth_headers(admin),
    )

    assert response.status_code == 422


def test_admin_can_ignore_unmatched_provider_row(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    unmatched = record_unmatched_provider_row(
        db_session,
        provider="sportsdata",
        season=2026,
        week=1,
        row={"PlayerID": "skip-1", "Name": "Bad Row"},
        reason="invalid provider payload: missing stat",
    )
    db_session.commit()

    response = client.post(
        f"/admin/scoring/unmatched-provider-rows/{unmatched.id}/ignore",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ignored"
    assert payload["resolved_by_user_id"] == admin.id
    db_session.expire_all()
    refreshed_unmatched = db_session.get(ProviderUnmatchedPlayerRow, unmatched.id)
    assert refreshed_unmatched.status == "ignored"
    assert refreshed_unmatched.resolved_at is not None


def test_admin_can_mark_unmatched_provider_row_resolved(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    unmatched = record_unmatched_provider_row(
        db_session,
        provider="espn",
        season=2026,
        week=1,
        row={"ESPNPlayerID": "resolved-1", "PlayerName": "Already Fixed", "School": "Texas"},
        reason="no local player matched provider row",
    )
    db_session.commit()

    response = client.post(
        f"/admin/scoring/unmatched-provider-rows/{unmatched.id}/resolve",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "resolved"
    assert payload["resolved_by_user_id"] == admin.id
    db_session.expire_all()
    refreshed_unmatched = db_session.get(ProviderUnmatchedPlayerRow, unmatched.id)
    assert refreshed_unmatched.status == "resolved"
    assert refreshed_unmatched.resolved_at is not None


def test_admin_scoring_routes_require_configured_admin(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    regular = _create_user(db_session, "regular@example.com")
    db_session.add(
        ScoringRun(
            season=2026,
            week=1,
            provider="espn",
            status="success",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            rows_fetched=10,
            rows_matched=8,
            rows_unmatched=2,
        )
    )
    db_session.commit()

    assert client.get("/admin/scoring/runs", headers=_auth_headers(regular)).status_code == 403

    response = client.get("/admin/scoring/runs", headers=_auth_headers(admin))
    assert response.status_code == 200
    assert response.json()["data"][0]["rows_fetched"] == 10


def test_admin_provider_identity_report_surfaces_missing_ids_and_duplicates(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    db_session.add_all(
        [
            Player(name="ESPN Only", position="QB", school="A", external_id="espn:1"),
            Player(name="SportsData Only", position="RB", school="B", external_id="sportsdata:2"),
            Player(name="No ID", position="WR", school="C", external_id=None),
            Player(name="Same Name", position="WR", school="D", external_id="espn:3"),
            Player(name="Same Name", position="WR", school="D", external_id="espn:4"),
        ]
    )
    mapped = Player(name="Mapped Both", position="QB", school="E", external_id=None)
    db_session.add(mapped)
    db_session.flush()
    db_session.add_all(
        [
            PlayerProviderId(
                player_id=mapped.id,
                provider="espn",
                provider_player_id="mapped-espn",
                match_confidence=100,
            ),
            PlayerProviderId(
                player_id=mapped.id,
                provider="sportsdata",
                provider_player_id="mapped-sd",
                match_confidence=100,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/admin/scoring/provider-identity", headers=_auth_headers(admin))

    assert response.status_code == 200
    payload = response.json()
    missing_by_name = {row["name"]: row for row in payload["missing_provider_ids"]}
    assert missing_by_name["ESPN Only"]["missing_sportsdata_id"] is True
    assert missing_by_name["SportsData Only"]["missing_espn_id"] is True
    assert missing_by_name["No ID"]["missing_espn_id"] is True
    assert missing_by_name["No ID"]["missing_sportsdata_id"] is True
    assert "Mapped Both" not in missing_by_name
    assert payload["duplicate_name_school_pairs"] == [{"name": "Same Name", "school": "D", "count": 2}]


def test_admin_provider_sync_status_shows_freshness_and_job_history(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    now = datetime.now(timezone.utc)
    db_session.add(
        ProviderSyncState(
            provider="sportsdata",
            feed="player_game_stats_week",
            scope_key='{"season":2026,"week":1}',
            status="ready",
            last_attempted_at=now,
            last_success_at=now,
            expires_at=now + timedelta(minutes=10),
        )
    )
    db_session.add(
        ProviderSyncJob(
            provider="sportsdata",
            feed="player_game_stats_week",
            season=2026,
            week=1,
            scope="season:2026:week:1",
            status="success",
            started_at=now,
            finished_at=now,
            rows_seen=3,
            rows_inserted=1,
            rows_updated=1,
            rows_rejected=1,
        )
    )
    db_session.commit()

    response = client.get("/admin/provider-sync/status?provider=sportsdata", headers=_auth_headers(admin))

    assert response.status_code == 200
    payload = response.json()
    assert payload["states"][0]["is_stale"] is False
    assert payload["states"][0]["last_successful_sync_at"] is not None
    assert payload["states"][0]["cache_expires_at"] is not None
    assert payload["recent_jobs"][0]["rows_rejected"] == 1


def test_admin_player_reconciliation_shows_raw_stats_and_breakdown(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    league, _home, _away, players, _matchup = create_scoring_fixture(db_session)

    from collegefootballfantasy_api.app.services.scoring_service import recalculate_league_week_scores

    recalculate_league_week_scores(db_session, league.id, 2026, 1)

    response = client.get(
        f"/admin/scoring/players/{players['qb'].id}/weeks/1?season=2026&league_id={league.id}",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["raw_stat"]["stats"]["PassingYards"] == 250
    assert payload["scores"][0]["breakdown_json"]["pass_yards"]["points"] == 10.0


def test_admin_can_rerun_preview_apply_and_list_scoring_corrections(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    league, _home, _away, players, _matchup = create_scoring_fixture(db_session)

    rerun_response = client.post(
        f"/admin/scoring/leagues/{league.id}/weeks/1/rerun?season=2026",
        headers=_auth_headers(admin),
    )
    assert rerun_response.status_code == 200
    assert rerun_response.json()["status"] == "rerun_complete"

    preview_response = client.post(
        f"/admin/scoring/leagues/{league.id}/weeks/1/stat-corrections/preview?season=2026",
        json={"player_id": players["qb"].id, "stats": {"PassingYards": 400, "PassingTouchdowns": 4}},
        headers=_auth_headers(admin),
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["status"] == "preview"
    assert preview["player_id"] == players["qb"].id
    assert preview["new_fantasy_points"] > preview["old_fantasy_points"]

    apply_response = client.post(
        f"/admin/scoring/leagues/{league.id}/weeks/1/stat-corrections?season=2026",
        json={
            "player_id": players["qb"].id,
            "stats": {"PassingYards": 400, "PassingTouchdowns": 4},
            "reason": "box score correction",
        },
        headers=_auth_headers(admin),
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert apply_payload["status"] == "stat_corrected"
    assert apply_payload["affected_league_ids"] == [league.id]

    audit_response = client.get(
        f"/admin/scoring/leagues/{league.id}/weeks/1/stat-corrections?season=2026",
        headers=_auth_headers(admin),
    )
    assert audit_response.status_code == 200
    audit_rows = audit_response.json()["data"]
    assert audit_rows[0]["player_id"] == players["qb"].id
    assert audit_rows[0]["reason"] == "box score correction"
    assert audit_rows[0]["affected_league_ids"] == [league.id]


def test_admin_scoring_correction_rejects_invalid_schema(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    league, _home, _away, players, _matchup = create_scoring_fixture(db_session)

    response = client.post(
        f"/admin/scoring/leagues/{league.id}/weeks/1/stat-corrections/preview?season=2026",
        json={"player_id": str(players["qb"].id), "stats": [], "extra": "not allowed"},
        headers=_auth_headers(admin),
    )

    assert response.status_code == 422


def test_admin_finalize_week_accepts_typed_body(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    league, _home, _away, _players, _matchup = create_scoring_fixture(db_session)

    response = client.post(
        f"/admin/scoring/leagues/{league.id}/weeks/1/finalize",
        json={"season": 2026},
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "final"


def test_admin_finalize_week_rejects_invalid_schema(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    league, _home, _away, _players, _matchup = create_scoring_fixture(db_session)

    response = client.post(
        f"/admin/scoring/leagues/{league.id}/weeks/1/finalize",
        json={"season": "2026"},
        headers=_auth_headers(admin),
    )

    assert response.status_code == 422


def test_admin_can_view_weekly_lock_readiness(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "admin_emails", "admin@example.com")
    admin = _create_user(db_session, "admin@example.com")
    db_session.add(Player(name="Admin Texas RB", position="RB", school="Texas"))
    upsert_team_provider_id(db_session, canonical_school="Texas", provider="sportsdata", provider_team_id="sd-texas")
    db_session.add(
        Game(
            external_id="admin-lock-readiness",
            provider="sportsdata",
            season=2026,
            week=1,
            start_date=datetime.now(timezone.utc) + timedelta(days=1),
            home_team="Texas",
            away_team="Oklahoma",
            home_provider_team_id="sd-texas",
            away_provider_team_id="sd-oklahoma",
        )
    )
    db_session.commit()

    response = client.get(
        "/admin/scoring/lock-readiness?season=2026&week=1&provider=sportsdata",
        headers=_auth_headers(admin),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["checked_schools"] == ["Texas"]
