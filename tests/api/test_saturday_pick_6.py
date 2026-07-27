from datetime import datetime, timedelta, timezone

from conftest import admin_headers

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.saturday_pick import SaturdayPickContest, SaturdayPickPlayer
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule


def _enable_pick_6(monkeypatch):
    monkeypatch.setattr(settings, "saturday_pick_6_enabled", True)
    monkeypatch.setattr(settings, "saturday_pick_6_public_enabled", True)


def _featured_players(db_session, *, position="QB", final_games=False):
    kickoff = datetime.now(timezone.utc) + timedelta(hours=4)
    players = []
    for index in range(6):
        player = Player(name=f"{position} Featured {index}", position=position, school=f"School {index}")
        db_session.add(player)
        db_session.flush()
        game = Game(
            season=2026,
            week=1,
            home_team=f"Opponent {index}",
            away_team=player.school,
            start_date=kickoff + timedelta(minutes=index),
            home_points=10 if final_games else None,
            away_points=20 if final_games else None,
        )
        db_session.add(game)
        db_session.flush()
        db_session.add(TeamSchedule(
            team_name=player.school,
            season=2026,
            week=1,
            game_id=game.id,
            opponent_name=game.home_team,
            location="away",
            is_bye=False,
            kickoff_at=game.start_date,
        ))
        if final_games:
            db_session.add(PlayerGameStat(
                player_id=player.id,
                game_id=game.id,
                season=2026,
                week=1,
                source="test",
                stats={"pass_yards": 200 + index * 25, "pass_tds": 1},
            ))
        players.append(player)
    db_session.commit()
    return players, kickoff


def _create_payload(players, lock_at, *, position="QB", **extra):
    return {
        "season": 2026,
        "week_number": 1,
        "contest_position": position,
        "featured_player_ids": [player.id for player in players],
        "lock_at": lock_at.isoformat(),
        **extra,
    }


def test_admin_rejects_mixed_position_and_wrong_field_size(client, db_session):
    players, kickoff = _featured_players(db_session)
    player = players[-1]
    player.position = "RB"
    db_session.commit()

    mixed = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff), headers=admin_headers(client))
    assert mixed.status_code == 422
    assert "match the contest position" in mixed.json()["detail"]

    player.position = "QB"
    db_session.commit()
    short = client.post(
        "/admin/saturday-pick-6",
        json=_create_payload(players[:5], kickoff),
        headers=admin_headers(client),
    )
    assert short.status_code == 422
    assert "exactly six" in short.json()["detail"]


def test_public_entry_can_change_before_lock_and_rejects_after_lock(client, db_session, monkeypatch):
    _enable_pick_6(monkeypatch)
    players, kickoff = _featured_players(db_session)
    headers = admin_headers(client)
    created = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff), headers=headers)
    assert created.status_code == 201
    contest_id = created.json()["id"]
    assert client.post(f"/admin/saturday-pick-6/{contest_id}/publish", json={}, headers=headers).status_code == 200

    signup = client.post("/auth/signup", json={"first_name": "Picker", "email": "picker@example.com", "password": "StrongPass123!"})
    user_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    first = client.put(f"/saturday-pick-6/{contest_id}/entry", json={"selected_pick_player_id": created.json()["players"][0]["id"]}, headers=user_headers)
    changed = client.put(f"/saturday-pick-6/{contest_id}/entry", json={"selected_pick_player_id": created.json()["players"][1]["id"]}, headers=user_headers)
    assert first.status_code == 200
    assert changed.status_code == 200
    assert changed.json()["selected_pick_player_id"] == created.json()["players"][1]["id"]

    from collegefootballfantasy_api.app.models.saturday_pick import SaturdayPickContest
    contest = db_session.get(SaturdayPickContest, contest_id)
    contest.lock_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    contest.status = "OPEN"
    db_session.commit()
    locked = client.put(f"/saturday-pick-6/{contest_id}/entry", json={"selected_pick_player_id": created.json()["players"][2]["id"]}, headers=user_headers)
    assert locked.status_code == 409


def test_finalization_marks_tied_winners_and_hides_sponsor_code_from_losers(client, db_session, monkeypatch):
    _enable_pick_6(monkeypatch)
    players, kickoff = _featured_players(db_session, final_games=True)
    headers = admin_headers(client)
    created = client.post(
        "/admin/saturday-pick-6",
        json=_create_payload(players, kickoff, sponsor_name="Example Sponsor", sponsor_code="WINNER-ONLY"),
        headers=headers,
    )
    assert created.status_code == 201
    contest_id = created.json()["id"]
    assert client.post(f"/admin/saturday-pick-6/{contest_id}/publish", json={}, headers=headers).status_code == 200

    # Force the first two players into an exact tie under canonical scoring.
    stats = db_session.query(PlayerGameStat).order_by(PlayerGameStat.player_id.asc()).all()
    stats[0].stats = {"pass_yards": 1_000, "pass_tds": 2}
    stats[1].stats = {"pass_yards": 1_000, "pass_tds": 2}
    db_session.commit()
    finalized = client.post(f"/admin/saturday-pick-6/{contest_id}/finalize", headers=headers)
    assert finalized.status_code == 200
    winning_ids = finalized.json()["winning_player_ids"]
    assert len(winning_ids) == 2

    signup = client.post("/auth/signup", json={"first_name": "Loser", "email": "loser@example.com", "password": "StrongPass123!"})
    user_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    contest = client.get(f"/saturday-pick-6/{contest_id}", headers=user_headers).json()
    losing_featured = next(row for row in contest["players"] if row["player_id"] not in winning_ids)
    # A finalized contest cannot accept a late pick; the public payload still must never disclose a code.
    assert contest["sponsor"]["code"] is None
    assert losing_featured["final_points"] is not None


def test_live_refresh_uses_canonical_stats_without_zeroing_delayed_players(client, db_session, monkeypatch):
    _enable_pick_6(monkeypatch)
    players, kickoff = _featured_players(db_session)
    headers = admin_headers(client)
    created = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff), headers=headers)
    contest_id = created.json()["id"]
    assert client.post(f"/admin/saturday-pick-6/{contest_id}/publish", json={}, headers=headers).status_code == 200

    featured = db_session.query(SaturdayPickPlayer).filter(SaturdayPickPlayer.contest_id == contest_id).order_by(SaturdayPickPlayer.id).all()
    contest = db_session.get(SaturdayPickContest, contest_id)
    contest.lock_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    contest.status = "OPEN"
    featured[0].game_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.add(PlayerGameStat(
        player_id=featured[0].player_id,
        game_id=featured[0].game_id,
        season=2026,
        week=1,
        source="test-live",
        stats={"rush_yards": 81, "rush_tds": 1},
    ))
    db_session.commit()

    refreshed = client.post(f"/admin/saturday-pick-6/{contest_id}/refresh", headers=headers)
    assert refreshed.status_code == 200
    payload = refreshed.json()
    assert payload["status"] == "SCORING"
    assert payload["players"][0]["scoring_status"] == "LIVE"
    assert payload["players"][0]["live_points"] > 0
    assert payload["players"][1]["live_points"] is None
    assert payload["players"][1]["scoring_status"] == "NOT_STARTED"

    active = client.get("/saturday-pick-6/active", params={"season": 2026, "week": 1}, headers=headers)
    results = client.get(f"/saturday-pick-6/{contest_id}/results", headers=headers)
    assert active.status_code == 200
    assert results.status_code == 200
