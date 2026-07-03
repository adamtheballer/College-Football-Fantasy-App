from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
import pytest
from sqlalchemy.exc import IntegrityError

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.draft_room import DraftPickCreate
from collegefootballfantasy_api.app.services.draft_service import create_real_draft_pick
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.draft_completion import finalize_draft_rosters_and_matchups
from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week
from collegefootballfantasy_api.app.services.matchup_probability import calculate_matchup_win_probability


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
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


def create_league(
    client,
    token: str,
    roster_slots: dict | None = None,
    draft_datetime_utc: str | None = None,
    max_teams: int = 1,
    kicker_enabled: bool = False,
) -> dict:
    draft_start = draft_datetime_utc or (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    payload = {
        "basics": {
            "name": "Draft Test League",
            "season_year": 2026,
            "max_teams": max_teams,
            "is_private": True,
            "description": "Draft room league",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": roster_slots or {"QB": 1},
            "playoff_teams": 4,
            "waiver_type": "faab",
            "trade_review_type": "commissioner",
            "superflex_enabled": False,
            "kicker_enabled": kicker_enabled,
            "defense_enabled": False,
        },
        "draft": {
            "draft_datetime_utc": draft_start,
            "timezone": "America/Los_Angeles",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }
    response = client.post(
        "/leagues",
        json=payload,
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def create_player(client, name: str = "Arch Manning", position: str = "QB") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": position,
                "school": "Texas",
                "image_url": None,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def join_league(client, league_id: int, suffix: str) -> str:
    token = create_user_and_token(client, suffix)
    response = client.post(f"/leagues/{league_id}/join", headers=auth_headers(token))
    assert response.status_code == 200
    return token


def fill_roster_except_k(db_session, league_id: int, team_id: int):
    players = [
        Player(name="Filled QB", position="QB", school="Texas"),
        Player(name="Filled RB 1", position="RB", school="Texas"),
        Player(name="Filled RB 2", position="RB", school="Texas"),
        Player(name="Filled WR 1", position="WR", school="Texas"),
        Player(name="Filled WR 2", position="WR", school="Texas"),
        Player(name="Filled TE", position="TE", school="Texas"),
        Player(name="Filled FLEX", position="RB", school="Texas"),
        Player(name="Bench QB", position="QB", school="Texas"),
        Player(name="Bench RB", position="RB", school="Texas"),
        Player(name="Bench WR 1", position="WR", school="Texas"),
        Player(name="Bench TE", position="TE", school="Texas"),
        Player(name="Bench WR 2", position="WR", school="Texas"),
    ]
    db_session.add_all(players)
    db_session.flush()
    slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BENCH", "BENCH", "BENCH", "BENCH", "BENCH"]
    db_session.add_all(
        [
            RosterEntry(
                league_id=league_id,
                team_id=team_id,
                player_id=player.id,
                slot=slot,
                status="active",
            )
            for player, slot in zip(players, slots, strict=True)
        ]
    )
    db_session.commit()


def test_draft_pick_persists_and_creates_roster_entry(client):
    token = create_user_and_token(client, "draft")
    league = create_league(client, token)
    player_id = create_player(client)

    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    room = room_response.json()
    assert room["picks"] == []
    assert room["can_make_pick"] is True
    assert room["user_team_id"] is not None

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    assert pick_response.status_code == 201
    updated_room = pick_response.json()
    assert len(updated_room["picks"]) == 1
    assert updated_room["picks"][0]["player_id"] == player_id
    assert updated_room["picks"][0]["team_id"] == updated_room["user_team_id"]

    roster_response = client.get(
        f"/teams/{updated_room['user_team_id']}/roster",
        headers=auth_headers(token),
    )
    assert roster_response.status_code == 200
    roster = roster_response.json()
    assert roster["total"] == 1
    assert roster["data"][0]["player"]["id"] == player_id


def test_duplicate_draft_pick_returns_409_and_does_not_create_extra_rows(client, db_session):
    token = create_user_and_token(client, "draft-duplicate")
    league = create_league(client, token, roster_slots={"QB": 2})
    player_id = create_player(client, "Duplicate Draft QB", "QB")

    first_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    second_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )

    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "player already drafted"
    assert (
        db_session.query(DraftPick)
        .filter(DraftPick.draft_id == draft.id, DraftPick.player_id == player_id)
        .count()
        == 1
    )
    assert (
        db_session.query(RosterEntry)
        .filter(RosterEntry.league_id == league["id"], RosterEntry.player_id == player_id)
        .count()
        == 1
    )


def test_draft_pick_integrity_error_returns_409_and_rolls_back(client, db_session, monkeypatch):
    token = create_user_and_token(client, "draft-integrity")
    league = create_league(client, token)
    player_id = create_player(client, "Integrity Rollback QB", "QB")
    league_row = db_session.get(League, league["id"])
    current_user = db_session.query(User).filter(User.email == "coach-draft-integrity@example.com").one()

    def raise_integrity_error():
        raise IntegrityError("INSERT draft pick", {}, Exception("duplicate"))

    monkeypatch.setattr(db_session, "commit", raise_integrity_error)

    with pytest.raises(HTTPException) as exc_info:
        create_real_draft_pick(
            db_session,
            league=league_row,
            payload=DraftPickCreate(player_id=player_id),
            current_user=current_user,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "draft pick conflicts with existing draft or roster state"
    assert db_session.query(DraftPick).filter(DraftPick.player_id == player_id).count() == 0
    assert db_session.query(RosterEntry).filter(RosterEntry.player_id == player_id).count() == 0


def test_draft_pick_rejects_before_scheduled_start(client, db_session):
    token = create_user_and_token(client, "draft-before-start")
    future_start = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    league = create_league(client, token, draft_datetime_utc=future_start)
    player_id = create_player(client, "Early Pick QB", "QB")

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "draft has not started yet"
    assert db_session.query(DraftPick).filter(DraftPick.player_id == player_id).count() == 0
    assert db_session.query(RosterEntry).filter(RosterEntry.player_id == player_id).count() == 0
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    assert draft.status == "scheduled"


def test_draft_pick_rejects_when_league_is_not_full(client, db_session):
    token = create_user_and_token(client, "draft-not-full")
    league = create_league(client, token, max_teams=2)
    player_id = create_player(client, "Full League Required QB", "QB")

    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    assert room_response.json()["can_make_pick"] is False

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "draft cannot start until the league is full"
    assert db_session.query(DraftPick).filter(DraftPick.player_id == player_id).count() == 0
    assert db_session.query(RosterEntry).filter(RosterEntry.player_id == player_id).count() == 0
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    assert draft.status == "scheduled"


def test_draft_pick_rejects_position_without_open_roster_slot(client, db_session):
    token = create_user_and_token(client, "draft-illegal-slot")
    roster_slots = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 5}
    league = create_league(client, token, roster_slots=roster_slots, kicker_enabled=True)
    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    team_id = room_response.json()["user_team_id"]
    fill_roster_except_k(db_session, league["id"], team_id)
    rb_id = create_player(client, "Illegal RB", "RB")

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": rb_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No open roster slot for this position."
    assert db_session.query(DraftPick).filter(DraftPick.player_id == rb_id).count() == 0
    assert db_session.query(RosterEntry).filter(RosterEntry.player_id == rb_id).count() == 0


def test_draft_pick_allows_kicker_when_only_k_slot_is_open(client, db_session):
    token = create_user_and_token(client, "draft-k-slot")
    roster_slots = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 5}
    league = create_league(client, token, roster_slots=roster_slots, kicker_enabled=True)
    room_response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(token),
    )
    assert room_response.status_code == 200
    team_id = room_response.json()["user_team_id"]
    fill_roster_except_k(db_session, league["id"], team_id)
    kicker_id = create_player(client, "Legal Kicker", "K")

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": kicker_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 201
    entry = db_session.query(RosterEntry).filter(RosterEntry.player_id == kicker_id).one()
    assert entry.slot == "K"


def test_draft_room_requires_membership(client):
    owner_token = create_user_and_token(client, "draft-owner")
    outsider_token = create_user_and_token(client, "draft-outsider")
    league = create_league(client, owner_token)

    response = client.get(
        f"/leagues/{league['id']}/draft-room",
        headers=auth_headers(outsider_token),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_draft_completion_finalizer_backfills_missing_roster_entries_once(client, db_session):
    owner_token = create_user_and_token(client, "roster-import-owner")
    league = create_league(client, owner_token, max_teams=1)
    first_player_id = create_player(client, "Import QB One", "QB")

    pick_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": first_player_id},
        headers=auth_headers(owner_token),
    )
    assert pick_response.status_code == 201

    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    pick = db_session.query(DraftPick).filter(DraftPick.draft_id == draft.id).one()
    existing = db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"]).one()
    db_session.delete(existing)
    db_session.commit()

    result = finalize_draft_rosters_and_matchups(db_session, db_session.get(League, league["id"]))
    assert result["rosters_backfilled"] == 1
    rows = db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"]).all()
    assert len(rows) == 1
    assert rows[0].player_id == first_player_id
    assert rows[0].team_id == pick.team_id

    second_result = finalize_draft_rosters_and_matchups(db_session, db_session.get(League, league["id"]))
    assert second_result["rosters_backfilled"] == 0
    assert db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"]).count() == 1


def test_roster_entries_are_league_scoped_and_same_player_can_exist_in_multiple_leagues(client, db_session):
    first_owner_token = create_user_and_token(client, "same-player-owner-a")
    second_owner_token = create_user_and_token(client, "same-player-owner-b")
    first_league = create_league(client, first_owner_token, max_teams=1)
    second_league = create_league(client, second_owner_token, max_teams=1)
    player_id = create_player(client, "Shared Player", "QB")

    assert client.post(
        f"/leagues/{first_league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(first_owner_token),
    ).status_code == 201
    assert client.post(
        f"/leagues/{second_league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(second_owner_token),
    ).status_code == 201

    rows = db_session.query(RosterEntry).filter(RosterEntry.player_id == player_id).all()
    assert len(rows) == 2
    assert {row.league_id for row in rows} == {first_league["id"], second_league["id"]}


def test_same_player_cannot_be_owned_twice_in_one_league(client, db_session):
    owner_token = create_user_and_token(client, "same-league-owner")
    league = create_league(client, owner_token, max_teams=1)
    player_id = create_player(client, "One League Player", "QB")

    first_pick = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(owner_token),
    )
    assert first_pick.status_code == 201

    existing_row = db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"]).one()
    db_session.add(
        RosterEntry(
            league_id=league["id"],
            team_id=existing_row.team_id,
            player_id=player_id,
            slot="BENCH",
            status="active",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_matchup_endpoint_returns_current_opponent_and_win_probability(client, db_session):
    owner_token = create_user_and_token(client, "matchup-owner")
    league = create_league(client, owner_token, max_teams=2)
    member_token = join_league(client, league["id"], "matchup-member")
    first_player_id = create_player(client, "Matchup QB One", "QB")
    second_player_id = create_player(client, "Matchup QB Two", "QB")

    assert client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": first_player_id},
        headers=auth_headers(owner_token),
    ).status_code == 201
    assert client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": second_player_id},
        headers=auth_headers(member_token),
    ).status_code == 201

    first_entry = db_session.query(RosterEntry).filter(RosterEntry.player_id == first_player_id).one()
    second_entry = db_session.query(RosterEntry).filter(RosterEntry.player_id == second_player_id).one()
    db_session.add_all(
        [
            WeeklyProjection(player_id=first_player_id, season=2026, week=1, fantasy_points=24.0, floor=16.0, ceiling=32.0),
            WeeklyProjection(player_id=second_player_id, season=2026, week=1, fantasy_points=12.0, floor=8.0, ceiling=18.0),
        ]
    )
    db_session.commit()

    matchup_rows = db_session.query(Matchup).filter(Matchup.league_id == league["id"]).all()
    assert matchup_rows
    week_one_matchups = [row for row in matchup_rows if row.week == 1]
    assert len(week_one_matchups) == 1
    assert {week_one_matchups[0].home_team_id, week_one_matchups[0].away_team_id} == {
        first_entry.team_id,
        second_entry.team_id,
    }

    response = client.get(
        f"/leagues/{league['id']}/matchup",
        headers=auth_headers(owner_token),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["opponent_team"] is not None
    assert payload["my_team"]["fantasy_team_id"] != payload["opponent_team"]["fantasy_team_id"]
    assert payload["my_team"]["projected_total"] == 24.0
    assert round(payload["my_team"]["win_probability"] + payload["opponent_team"]["win_probability"], 2) == 100.0


def test_non_league_members_cannot_view_roster_matchup_waivers_or_settings(client):
    owner_token = create_user_and_token(client, "tabs-owner")
    outsider_token = create_user_and_token(client, "tabs-outsider")
    league = create_league(client, owner_token, max_teams=1)

    for path in ("roster", "matchup", "waivers", "settings-view"):
        response = client.get(
            f"/leagues/{league['id']}/{path}",
            headers=auth_headers(outsider_token),
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "league membership required"


def test_waiver_available_players_are_scoped_to_current_league(client):
    first_owner_token = create_user_and_token(client, "waiver-owner-a")
    second_owner_token = create_user_and_token(client, "waiver-owner-b")
    first_league = create_league(client, first_owner_token, max_teams=1)
    second_league = create_league(client, second_owner_token, max_teams=1)
    owned_player_id = create_player(client, "Scoped Waiver Owned QB", "QB")
    available_player_id = create_player(client, "Scoped Waiver Available QB", "QB")

    first_pick = client.post(
        f"/leagues/{first_league['id']}/draft-picks",
        json={"player_id": owned_player_id},
        headers=auth_headers(first_owner_token),
    )
    assert first_pick.status_code == 201

    first_response = client.get(
        f"/leagues/{first_league['id']}/waivers",
        headers=auth_headers(first_owner_token),
    )
    second_response = client.get(
        f"/leagues/{second_league['id']}/waivers",
        headers=auth_headers(second_owner_token),
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_available_ids = {player["id"] for player in first_response.json()["available_players"]}
    second_available_ids = {player["id"] for player in second_response.json()["available_players"]}
    assert owned_player_id not in first_available_ids
    assert available_player_id in first_available_ids
    assert owned_player_id in second_available_ids


def test_roster_endpoint_returns_zero_projection_and_ir_capacity(client):
    owner_token = create_user_and_token(client, "roster-view-owner")
    league = create_league(client, owner_token, max_teams=1)
    player_id = create_player(client, "Projection Missing QB", "QB")
    assert client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(owner_token),
    ).status_code == 201

    response = client.get(f"/leagues/{league['id']}/roster", headers=auth_headers(owner_token))
    assert response.status_code == 200
    payload = response.json()
    assert payload["ir_slots"] == 1
    assert payload["roster"][0]["projected_points"] == 0.0
    assert payload["roster"][0]["is_ir"] is False


def test_matchup_probability_helper_behaves_safely():
    even = calculate_matchup_win_probability(100, 100, 100, 100)
    assert even == (50.0, 50.0)
    favored = calculate_matchup_win_probability(140, 100, 100, 100)
    assert favored[0] > favored[1]
    assert round(favored[0] + favored[1], 1) == 100.0


def test_calendar_week_before_season_start_is_week_one():
    assert calendar_cfb_week(2026, datetime(2026, 6, 1, tzinfo=timezone.utc)) == 1


def test_calendar_week_increments_during_season():
    assert calendar_cfb_week(2026, datetime(2026, 9, 8, tzinfo=timezone.utc)) >= 3
