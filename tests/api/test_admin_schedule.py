from fastapi.testclient import TestClient

from collegefootballfantasy_api.app.services.schedule_time_sync import ScheduleSyncSummary
from conftest import admin_headers


def _summary() -> ScheduleSyncSummary:
    summary = ScheduleSyncSummary(season=2026, week=2, source="espn", games_fetched=4, games_matched=4, games_updated=3)
    return summary.finish()


def test_schedule_sync_endpoint_requires_an_admin(client: TestClient):
    response = client.post("/admin/schedules/sync", json={"season_year": 2026, "week": 2})
    assert response.status_code == 401


def test_schedule_sync_endpoint_uses_explicit_source_and_returns_summary(client: TestClient, monkeypatch):
    import collegefootballfantasy_api.app.api.routes.admin_schedule as route

    captured: dict = {}

    def fake_sync(_db, **kwargs):
        captured.update(kwargs)
        return _summary()

    monkeypatch.setattr(route, "sync_schedule_times", fake_sync)
    response = client.post(
        "/admin/schedules/sync",
        headers=admin_headers(client),
        json={"season_year": 2026, "week": 2, "source": "espn", "force_current_week": True},
    )

    assert response.status_code == 200
    assert response.json()["games_updated"] == 3
    assert captured["source"] == "espn"
    assert captured["force_current_week"] is True
    assert isinstance(captured["actor_user_id"], int)
