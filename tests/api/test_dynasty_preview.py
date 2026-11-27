"""Dynasty HTTP contract and durable lifecycle; all data is synthetic."""

from datetime import date

import pytest
from sqlalchemy import func, select

from conftest import TestingSessionLocal
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import create_access_token
from collegefootballfantasy_api.app.models.dynasty import (
    DynastyPickAsset,
    DynastyPlayerSeason,
    DynastyRoster,
)
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.dynasty import annual_order, dynasty_value


@pytest.fixture
def preview(client, monkeypatch):
    monkeypatch.setattr(settings, "dynasty_preview_enabled", True)
    monkeypatch.setattr(settings, "environment", "test")
    with TestingSessionLocal() as db:
        users = [
            User(
                first_name=f"Manager{i}",
                email=f"dynasty{i}@example.com",
                password_hash="test",
                api_token=f"dynasty{i}",
                is_admin=i == 0,
            )
            for i in range(4)
        ]
        db.add_all(users)
        players = [
            Player(
                name=f"Prospect {i:02}",
                school="Arizona State",
                position="RB",
                player_class="Freshman",
                raw_cfb27_rating=80,
                current_value_rating=77,
            )
            for i in range(24)
        ]
        db.add_all(players)
        db.commit()
        headers = [
            {
                "Authorization": f"Bearer {create_access_token(user_id=u.id, email=u.email)[0]}"
            }
            for u in users
        ]
        ids = [p.id for p in players]
    facts = [
        {
            "player_id": pid,
            "season": 2027,
            "entry_season": 2026,
            "school": "Arizona State",
            "academic_class": "SO",
            "eligible": True,
            "source_url": "https://example.edu/roster",
            "base_value": 80,
        }
        for pid in ids[:12]
    ]
    assert (
        client.post(
            "/dynasty/catalog", headers=headers[0], json={"data": facts}
        ).status_code
        == 200
    )
    return client, headers, ids


def create(preview, owner=0, **overrides):
    client, headers, _ = preview
    payload = dict(
        name="2027 Dynasty",
        season=2027,
        team_count=2,
        roster_limit=8,
        startup_rounds=2,
        freshman_rounds=1,
        future_pick_years=2,
    )
    payload.update(overrides)
    r = client.post("/dynasty/leagues", headers=headers[owner], json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def full(preview, **overrides):
    client, headers, _ = preview
    state = create(preview, **overrides)
    r = client.post(
        "/dynasty/join",
        headers=headers[1],
        json={"invite_code": state["invite_code"], "team_name": "Rivals"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def post(preview, state, path, owner=0, payload=None, expected=200):
    client, headers, _ = preview
    r = client.post(
        f'/dynasty/leagues/{state["league_id"]}/{path}',
        headers=headers[owner],
        json=payload,
    )
    assert r.status_code == expected, r.text
    return r.json()


def finish_draft(preview, state):
    client, headers, ids = preview
    users_by_team = {t["id"]: 0 if t["name"] != "Rivals" else 1 for t in state["teams"]}
    while state["next_pick_id"]:
        pick = next(p for p in state["picks"] if p["id"] == state["next_pick_id"])
        pool = client.get(
            f'/dynasty/leagues/{state["league_id"]}/pool', headers=headers[0]
        ).json()
        state = post(
            preview,
            state,
            f'picks/{pick["id"]}',
            users_by_team[pick["owner_team_id"]],
            {"player_id": pool["data"][0]["player_id"]},
        )
    return state


def test_disabled_and_future_only(preview, monkeypatch):
    client, headers, _ = preview
    monkeypatch.setattr(settings, "dynasty_preview_enabled", False)
    assert client.get("/dynasty/capabilities", headers=headers[0]).status_code == 404
    monkeypatch.setattr(settings, "dynasty_preview_enabled", True)
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "current_season_year", 2026)
    assert client.get("/dynasty/capabilities", headers=headers[0]).status_code == 404
    monkeypatch.setattr(settings, "environment", "test")
    assert client.get("/dynasty/capabilities").status_code == 401
    payload = dict(
        name="Bad season",
        season=2026,
        team_count=2,
        roster_limit=8,
        startup_rounds=2,
        freshman_rounds=1,
    )
    assert (
        client.post("/dynasty/leagues", headers=headers[0], json=payload).status_code
        == 422
    )
    assert not any(
        k.startswith("/dynasty") for k in client.get("/openapi.json").json()["paths"]
    )


def test_startup_snake_retry_ownership_and_redraft_isolation(preview):
    client, headers, ids = preview
    state = full(preview)
    assert (
        client.get(
            f'/dynasty/leagues/{state["league_id"]}', headers=headers[2]
        ).status_code
        == 403
    )
    post(preview, state, "start", owner=1, expected=403)
    state = post(preview, state, "start")
    assert post(preview, state, "start")["order"] == state["order"]
    picks = sorted(
        [p for p in state["picks"] if p["season"] == 2027],
        key=lambda p: p["overall_pick"],
    )
    assert [p["original_team_id"] for p in picks] == state["order"] + list(
        reversed(state["order"])
    )
    pick = picks[0]
    owner = (
        0
        if next(t for t in state["teams"] if t["id"] == pick["owner_team_id"])["name"]
        != "Rivals"
        else 1
    )
    post(
        preview,
        state,
        f'picks/{pick["id"]}',
        1 - owner,
        {"player_id": ids[0]},
        expected=403,
    )
    state = post(preview, state, f'picks/{pick["id"]}', owner, {"player_id": ids[0]})
    assert (
        post(preview, state, f'picks/{pick["id"]}', owner, {"player_id": ids[0]})[
            "pick_cursor"
        ]
        == 1
    )
    post(
        preview,
        state,
        f'picks/{pick["id"]}',
        owner,
        {"player_id": ids[1]},
        expected=409,
    )
    state = finish_draft(preview, state)
    assert state["status"] == "complete" and len(state["rosters"]) == 4
    assert all(r["value"]["academic_class"] == "SO" for r in state["rosters"])
    with TestingSessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(League)) == 0
        assert db.scalar(select(func.count()).select_from(RosterEntry)) == 0
        assert all(
            p.current_value_rating == 77 and p.raw_cfb27_rating == 80
            for p in db.scalars(select(Player))
        )


def test_freshmen_rollover_retains_transfers_and_does_not_guess_departures(preview):
    client, headers, ids = preview
    state = finish_draft(preview, post(preview, full(preview), "start"))
    a, b = [t["id"] for t in state["teams"]]
    departed = state["rosters"][0]["player_id"]
    facts = [
        dict(
            player_id=ids[i],
            season=2028,
            entry_season=2028 if i in (12, 13) else 2027,
            school="Arizona State",
            academic_class="FR" if i != 15 else "RSFR",
            eligible=True,
            source_url="https://example.edu/2028",
        )
        for i in (12, 13, 14, 15)
    ]
    facts += [
        dict(
            player_id=departed,
            season=2028,
            entry_season=2026,
            school="Arizona State",
            academic_class="JR",
            eligible=False,
            source_url="https://example.edu/departures",
        )
    ]
    assert (
        client.post(
            "/dynasty/catalog", headers=headers[0], json={"data": facts}
        ).status_code
        == 200
    )
    results = [
        {
            "team_id": a,
            "wins": 0,
            "losses": 10,
            "points_for": 100,
            "playoff_finish": None,
        },
        {"team_id": b, "wins": 10, "losses": 0, "points_for": 200, "playoff_finish": 1},
    ]
    state = post(preview, state, "close", payload={"results": results})
    snapshot = client.get(
        f'/dynasty/leagues/{state["league_id"]}/history/2027', headers=headers[1]
    ).json()
    assert len(snapshot["rosters"]) == 4
    state = post(preview, state, "rollover")
    assert state["current_season"] == 2028 and state["order"] == [a, b]
    assert len(state["rosters"]) == 3 and departed not in [
        r["player_id"] for r in state["rosters"]
    ]
    assert all(r["value"] is None for r in state["rosters"])
    pool = client.get(
        f'/dynasty/leagues/{state["league_id"]}/pool?limit=1', headers=headers[0]
    ).json()
    assert pool["total"] == 2 and len(pool["data"]) == 1
    assert (
        client.get(
            f'/dynasty/leagues/{state["league_id"]}/pool?limit=101', headers=headers[0]
        ).status_code
        == 422
    )
    state = finish_draft(preview, post(preview, state, "start"))
    assert len(state["rosters"]) == 5
    assert (
        snapshot
        == client.get(
            f'/dynasty/leagues/{state["league_id"]}/history/2027', headers=headers[1]
        ).json()
    )


def test_trade_consent_stale_atomicity_and_pick_origin(preview):
    client, headers, ids = preview
    state = full(preview)
    a, b = [t["id"] for t in state["teams"]]
    ap = next(
        p for p in state["picks"] if p["season"] == 2027 and p["owner_team_id"] == a
    )
    bp = next(
        p for p in state["picks"] if p["season"] == 2028 and p["owner_team_id"] == b
    )
    offer = {
        "from_team_id": a,
        "to_team_id": b,
        "give": [{"kind": "pick", "id": ap["id"]}],
        "receive": [{"kind": "pick", "id": bp["id"]}],
    }
    state = post(preview, state, "trades", payload=offer, expected=201)
    stale = state["trades"][0]["id"]
    state = post(preview, state, "trades", payload=offer, expected=201)
    tid = state["trades"][0]["id"]
    post(preview, state, f"trades/{tid}/accept", expected=403)
    state = post(preview, state, f"trades/{tid}/accept", owner=1)
    assert (
        post(preview, state, f"trades/{tid}/accept", owner=1)["trades"][0]["status"]
        == "accepted"
    )
    post(preview, state, f"trades/{stale}/accept", owner=1, expected=409)
    transferred = next(p for p in state["picks"] if p["id"] == ap["id"])
    assert transferred["original_team_id"] == a and transferred["owner_team_id"] == b
    state = finish_draft(preview, post(preview, state, "start"))
    assert sum(r["team_id"] == b for r in state["rosters"]) == 3
    # Exchange rostered players atomically while preserving roster-entry IDs.
    ar = next(r for r in state["rosters"] if r["team_id"] == a)
    br = next(r for r in state["rosters"] if r["team_id"] == b)
    offer.update(
        give=[{"kind": "player", "id": ar["player_id"]}],
        receive=[{"kind": "player", "id": br["player_id"]}],
    )
    state = post(preview, state, "trades", payload=offer, expected=201)
    state = post(preview, state, f'trades/{state["trades"][0]["id"]}/accept', owner=1)
    assert next(r for r in state["rosters"] if r["id"] == ar["id"])["team_id"] == b


def test_catalog_admin_and_unreviewed_fact_and_capacity(preview):
    client, headers, ids = preview
    fact = dict(
        player_id=ids[12],
        season=2027,
        entry_season=2027,
        school="Arizona State",
        academic_class="FR",
        eligible=True,
        source_url="https://example.edu/roster",
    )
    assert (
        client.post(
            "/dynasty/catalog", headers=headers[1], json={"data": [fact]}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/dynasty/catalog", headers=headers[0], json={"data": [fact, fact]}
        ).status_code
        == 422
    )
    fact["source_url"] = "http://example.edu/roster"
    assert (
        client.post(
            "/dynasty/catalog", headers=headers[0], json={"data": [fact]}
        ).status_code
        == 422
    )
    state = full(preview, roster_limit=2)
    a, b = [t["id"] for t in state["teams"]]
    ap, bp = [
        next(
            p for p in state["picks"] if p["season"] == 2027 and p["owner_team_id"] == t
        )
        for t in (a, b)
    ]
    offer = {
        "from_team_id": a,
        "to_team_id": b,
        "give": [{"kind": "pick", "id": ap["id"]}],
        "receive": [
            {
                "kind": "pick",
                "id": next(
                    p
                    for p in state["picks"]
                    if p["season"] == 2028 and p["owner_team_id"] == b
                )["id"],
            }
        ],
    }
    state = post(preview, state, "trades", payload=offer, expected=201)
    state = post(preview, state, f'trades/{state["trades"][0]["id"]}/accept', owner=1)
    post(
        preview, state, "start", expected=409
    )  # recipient now owns three picks but only two slots


def test_order_and_value_policy():
    results = [
        dict(
            team_id=i,
            wins=i,
            losses=10 - i,
            ties=0,
            points_for=100 + i,
            playoff_finish=None,
        )
        for i in range(1, 5)
    ]
    results[0]["playoff_finish"] = 1
    results[2]["playoff_finish"] = 2
    assert annual_order(results) == [2, 4, 3, 1]
    for r, rank in zip(results, [1, 4, 2, 3]):
        r["playoff_finish"] = rank
    assert annual_order(results) == [2, 4, 3, 1]
    fact = DynastyPlayerSeason(
        season=2027, academic_class="FR", base_value=80, birth_date=None
    )
    assert dynasty_value(fact)["age"] is None and dynasty_value(fact)["estimate"] == 96
    fact.birth_date = date(2009, 8, 2)
    assert dynasty_value(fact)["age"] == 17
    fact.academic_class = "SR"
    assert dynasty_value(fact)["estimate"] < 96


def test_cross_league_assets_and_stale_player_trade(preview):
    client, headers, ids = preview
    state = finish_draft(preview, post(preview, full(preview), "start"))
    other = create(preview, owner=2)
    a, b = [t["id"] for t in state["teams"]]
    ar = next(r for r in state["rosters"] if r["team_id"] == a)
    br = next(r for r in state["rosters"] if r["team_id"] == b)
    offer = {
        "from_team_id": a,
        "to_team_id": b,
        "give": [{"kind": "player", "id": ar["player_id"]}],
        "receive": [{"kind": "player", "id": br["player_id"]}],
    }
    bad = {**offer, "give": [{"kind": "pick", "id": other["picks"][0]["id"]}]}
    post(preview, state, "trades", payload=bad, expected=409)
    bad = {**offer, "to_team_id": other["teams"][0]["id"]}
    post(preview, state, "trades", payload=bad, expected=422)
    state = post(preview, state, "trades", payload=offer, expected=201)
    tid = state["trades"][0]["id"]
    post(preview, state, f'rosters/{ar["id"]}/drop', owner=1, expected=403)
    state = post(preview, state, f'rosters/{ar["id"]}/drop')
    post(preview, state, f"trades/{tid}/accept", owner=1, expected=409)
    pool = client.get(
        f'/dynasty/leagues/{state["league_id"]}/pool', headers=headers[0]
    ).json()
    assert ar["player_id"] not in [p["player_id"] for p in pool["data"]]
    current = client.get(
        f'/dynasty/leagues/{state["league_id"]}', headers=headers[1]
    ).json()
    assert (
        next(r for r in current["rosters"] if r["player_id"] == br["player_id"])[
            "team_id"
        ]
        == b
    )


def test_postgres_concurrent_pick_and_trade_acceptance(preview):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from conftest import engine

    if engine.dialect.name != "postgresql":
        pytest.skip("row-lock behavior requires disposable PostgreSQL")
    client, headers, ids = preview
    state = post(preview, full(preview), "start")
    pick = next(p for p in state["picks"] if p["id"] == state["next_pick_id"])
    owner = 0 if pick["owner_team_id"] == state["teams"][0]["id"] else 1
    barrier = Barrier(2)

    def select_player(pid):
        barrier.wait(timeout=10)
        return client.post(
            f'/dynasty/leagues/{state["league_id"]}/picks/{pick["id"]}',
            headers=headers[owner],
            json={"player_id": pid},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(select_player, ids[:2])) == [200, 409]
    with TestingSessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(DynastyRoster)) == 1
    state = client.get(
        f'/dynasty/leagues/{state["league_id"]}', headers=headers[0]
    ).json()
    a, b = [t["id"] for t in state["teams"]]
    ap, bp = [
        next(
            p for p in state["picks"] if p["season"] == 2028 and p["owner_team_id"] == t
        )
        for t in (a, b)
    ]
    offer = {
        "from_team_id": a,
        "to_team_id": b,
        "give": [{"kind": "pick", "id": ap["id"]}],
        "receive": [{"kind": "pick", "id": bp["id"]}],
    }
    tids = []
    for _ in range(2):
        state = post(preview, state, "trades", payload=offer, expected=201)
        tids.append(state["trades"][0]["id"])
    barrier = Barrier(2)

    def accept(tid):
        barrier.wait(timeout=10)
        return client.post(
            f'/dynasty/leagues/{state["league_id"]}/trades/{tid}/accept',
            headers=headers[1],
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(accept, tids)) == [200, 409]
    current = client.get(
        f'/dynasty/leagues/{state["league_id"]}', headers=headers[0]
    ).json()
    assert sum(t["status"] == "accepted" for t in current["trades"]) == 1


def test_trade_capacity_failure_preserves_all_assets(preview):
    client, headers, ids = preview
    state = finish_draft(preview, post(preview, full(preview, roster_limit=2), "start"))
    a, b = [t["id"] for t in state["teams"]]
    ap = next(
        p for p in state["picks"] if p["season"] == 2028 and p["owner_team_id"] == a
    )
    br = next(r for r in state["rosters"] if r["team_id"] == b)
    offer = {
        "from_team_id": a,
        "to_team_id": b,
        "give": [{"kind": "pick", "id": ap["id"]}],
        "receive": [{"kind": "player", "id": br["player_id"]}],
    }
    state = post(preview, state, "trades", payload=offer, expected=201)
    post(
        preview,
        state,
        f'trades/{state["trades"][0]["id"]}/accept',
        owner=1,
        expected=409,
    )
    current = client.get(
        f'/dynasty/leagues/{state["league_id"]}', headers=headers[0]
    ).json()
    assert current["rosters"] == state["rosters"]
    assert (
        next(p for p in current["picks"] if p["id"] == ap["id"])["owner_team_id"] == a
    )
    assert current["trades"][0]["status"] == "pending"


def test_shared_draft_board_keeps_selected_players_and_stable_ranks(preview):
    client, headers, ids = preview
    state = post(preview, full(preview), "start")
    path = f'/dynasty/leagues/{state["league_id"]}/pool?available_only=false'
    before = client.get(path, headers=headers[0]).json()
    first = before["data"][0]
    asset = next(p for p in state["picks"] if p["id"] == state["next_pick_id"])
    owner = 0 if asset["owner_team_id"] == state["teams"][0]["id"] else 1
    state = post(
        preview,
        state,
        f'picks/{asset["id"]}',
        owner=owner,
        payload={"player_id": first["player_id"]},
    )
    after = client.get(path, headers=headers[0]).json()
    assert [(p["player_id"], p["draft_rank"]) for p in after["data"]] == [
        (p["player_id"], p["draft_rank"]) for p in before["data"]
    ]
    assert state["draft_picks"][0]["player_name"] == first["name"]
    assert state["draft_picks"][0]["team_id"] == asset["owner_team_id"]
    entry = next(r for r in state["rosters"] if r["player_id"] == first["player_id"])
    state = post(preview, state, f'rosters/{entry["id"]}/drop', owner=owner)
    assert state["draft_picks"][0]["player_name"] == first["name"]
    assert first["player_id"] in [
        p["player_id"] for p in client.get(path, headers=headers[0]).json()["data"]
    ]
    available = client.get(
        f'/dynasty/leagues/{state["league_id"]}/pool', headers=headers[0]
    ).json()
    assert first["player_id"] not in [p["player_id"] for p in available["data"]]
