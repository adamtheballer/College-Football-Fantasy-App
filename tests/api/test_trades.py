import pytest

from collegefootballfantasy_api.app.api.routes.trades import (
    DEFAULT_ROSTER_SLOTS,
    _normalize_roster_slots,
)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "trade") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-{suffix}@example.com",
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def trade_payload() -> dict:
    return {
        "receive_ids": [1],
        "give_ids": [2],
        "season": 2026,
        "week": 1,
        "league_size": 12,
        "roster_slots": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "BE": 4, "IR": 1},
    }


def test_trade_analyze_requires_auth(client):
    response = client.post("/trade/analyze", json=trade_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "missing auth token"


def test_trade_analyze_allows_authenticated_user(client):
    token = create_user_and_token(client)

    response = client.post(
        "/trade/analyze",
        json=trade_payload(),
        headers=auth_headers(token),
    )

    assert response.status_code == 200


def test_normalize_roster_slots_uses_payload_values():
    slots = _normalize_roster_slots(
        {
            "QB": 2,
            "RB": 1,
            "WR": 3,
            "TE": 2,
            "K": 0,
            "BE": 8,
            "IR": 2,
        }
    )

    assert slots == {
        "QB": 2,
        "RB": 1,
        "WR": 3,
        "TE": 2,
        "K": 0,
        "BE": 8,
        "IR": 2,
    }


def test_normalize_roster_slots_accepts_bench_alias():
    slots = _normalize_roster_slots({"BENCH": 6})

    assert slots["BE"] == 6


def test_normalize_roster_slots_preserves_defaults_for_missing_values():
    slots = _normalize_roster_slots({"QB": 2})

    assert slots["QB"] == 2
    assert slots["RB"] == DEFAULT_ROSTER_SLOTS["RB"]
    assert slots["BE"] == DEFAULT_ROSTER_SLOTS["BE"]


def test_normalize_roster_slots_rejects_non_numeric_values():
    with pytest.raises((TypeError, ValueError)):
        _normalize_roster_slots({"QB": "bad"})  # type: ignore[dict-item]
