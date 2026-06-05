from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from api.app.models.draft import Draft
from api.app.models.draft_pick import DraftPick
from api.app.models.league import League
from api.app.models.league_settings import LeagueSettings
from api.app.models.roster import RosterEntry
from api.app.models.user import User
from api.app.services import draft_service


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"draft-conflict-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_league(client, token: str) -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": "Draft Conflict League",
                "season_year": 2026,
                "max_teams": 12,
                "is_private": False,
                "description": None,
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 2},
                "playoff_teams": 4,
                "waiver_type": "faab",
                "trade_review_type": "commissioner",
                "superflex_enabled": False,
                "kicker_enabled": True,
                "defense_enabled": False,
            },
            "draft": {
                "draft_datetime_utc": "2026-08-19T18:00:00Z",
                "timezone": "America/Los_Angeles",
                "draft_type": "snake",
                "pick_timer_seconds": 90,
            },
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def create_player(client, name: str = "Conflict QB") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": "QB",
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
    timer_row = draft_service._get_or_create_draft_timer_state(db_session, draft_row.id)
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(timer_row)
    db_session.commit()


def test_drafting_same_player_twice_returns_409_without_duplicates(client, db_session):
    token = create_user_and_token(client, "same-player")
    league = create_league(client, token)
    player_id = create_player(client)
    force_draft_live(db_session, league_id=league["id"])

    first_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )
    assert first_response.status_code == 201

    force_draft_live(db_session, league_id=league["id"])
    duplicate_response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] in {
        "player already drafted",
        "player already on a league roster",
        "draft state changed; refresh and try again",
    }

    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    assert db_session.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count() == 1
    assert db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"], RosterEntry.player_id == player_id).count() == 1

    room_response = client.get(f"/leagues/{league['id']}/draft-room", headers=auth_headers(token))
    assert room_response.status_code == 200
    room = room_response.json()
    assert len(room["picks"]) == 1
    assert room["drafted_player_ids"] == [player_id]
    assert room["current_pick"] == 2


def test_get_draft_room_state_returns_current_pick_and_team(client, db_session):
    token = create_user_and_token(client, "room-state")
    league = create_league(client, token)
    force_draft_live(db_session, league_id=league["id"])
    league_row = db_session.get(League, league["id"])
    user = db_session.query(User).filter(User.email == "draft-conflict-room-state@example.com").one()

    room = draft_service.get_draft_room_state(db_session, league_row, user)

    assert room.current_pick == 1
    assert room.current_round == 1
    assert room.current_round_pick == 1
    assert room.current_team_id == room.user_team_id
    assert room.can_make_pick is True


def test_successful_real_draft_pick_creates_exactly_one_pick_and_roster_entry(client, db_session):
    token = create_user_and_token(client, "success")
    league = create_league(client, token)
    player_id = create_player(client, "Success QB")
    force_draft_live(db_session, league_id=league["id"])

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 201, response.text
    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    pick = db_session.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).one()
    roster = db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"]).one()
    assert pick.overall_pick == 1
    assert pick.round_number == 1
    assert pick.round_pick == 1
    assert pick.player_id == player_id
    assert roster.player_id == player_id
    assert roster.team_id == pick.team_id


def test_not_current_team_owner_cannot_pick(client, db_session):
    commissioner_token = create_user_and_token(client, "turn-commissioner")
    member_token = create_user_and_token(client, "turn-member")
    league = create_league(client, commissioner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200, join_response.text
    player_id = create_player(client, "Wrong Turn QB")
    force_draft_live(db_session, league_id=league["id"])

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(member_token),
    )

    assert response.status_code == 403
    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    assert db_session.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count() == 0
    assert db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"]).count() == 0


def test_commissioner_can_pick_for_current_team(client, db_session):
    commissioner_token = create_user_and_token(client, "commissioner-pick")
    member_token = create_user_and_token(client, "commissioner-member")
    league = create_league(client, commissioner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200, join_response.text
    player_id = create_player(client, "Commissioner Pick QB")
    force_draft_live(db_session, league_id=league["id"])

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(commissioner_token),
    )

    assert response.status_code == 201, response.text
    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    assert db_session.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count() == 1
    assert db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"]).count() == 1


def test_draft_transitions_scheduled_to_live_on_first_successful_pick(client, db_session):
    token = create_user_and_token(client, "scheduled-start")
    league = create_league(client, token)
    player_id = create_player(client, "Scheduled Start QB")

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 201, response.text
    room = response.json()
    assert room["status"] == "live"
    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    league_row = db_session.get(League, league["id"])
    assert draft_row.status == "live"
    assert league_row.status == "draft_live"
    assert draft_row.current_pick_started_at is not None
    assert draft_row.current_pick_expires_at is not None


def test_draft_completion_sets_statuses(client, db_session):
    token = create_user_and_token(client, "completion")
    league = create_league(client, token)
    player_id = create_player(client, "Completion QB")
    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).one()
    settings_row.roster_slots_json = {"QB": 1}
    db_session.add(settings_row)
    force_draft_live(db_session, league_id=league["id"])

    response = client.post(
        f"/leagues/{league['id']}/draft-picks",
        json={"player_id": player_id},
        headers=auth_headers(token),
    )

    assert response.status_code == 201, response.text
    room = response.json()
    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    league_row = db_session.get(League, league["id"])
    assert room["is_complete"] is True
    assert room["status"] == "completed"
    assert draft_row.status == "completed"
    assert draft_row.completed_at is not None
    assert draft_row.current_pick_expires_at is None
    assert league_row.status == "post_draft"


def test_integrity_error_returns_409_and_rolls_back(client, db_session, monkeypatch):
    token = create_user_and_token(client, "integrity")
    league = create_league(client, token)
    player_id = create_player(client, "Integrity QB")
    force_draft_live(db_session, league_id=league["id"])
    league_row = db_session.get(League, league["id"])
    user = db_session.query(User).filter(User.email == "draft-conflict-integrity@example.com").one()

    def raise_integrity_error(*_args, **_kwargs):
        raise IntegrityError(
            statement="insert into draft_picks",
            params={},
            orig=Exception("uq_draft_picks_draft_player"),
        )

    monkeypatch.setattr(db_session, "flush", raise_integrity_error)

    with pytest.raises(HTTPException) as exc_info:
        draft_service.create_real_draft_pick(
            db_session,
            league_row,
            draft_service.DraftPickCreate(player_id=player_id),
            user,
        )

    assert exc_info.value.status_code == 409
    monkeypatch.undo()
    draft_row = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    assert db_session.query(DraftPick).filter(DraftPick.draft_id == draft_row.id).count() == 0
    assert db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"]).count() == 0


def test_duplicate_roster_insert_integrity_error_returns_409(client, db_session):
    token = create_user_and_token(client, "roster-integrity")
    league = create_league(client, token)
    player_id = create_player(client, "Roster Conflict QB")
    room = client.get(f"/leagues/{league['id']}/draft-room", headers=auth_headers(token)).json()
    team_id = room["user_team_id"]

    first_response = client.post(
        f"/teams/{team_id}/roster",
        json={"player_id": player_id, "slot": "QB", "status": "active"},
        headers=auth_headers(token),
    )
    assert first_response.status_code == 201

    settings_row = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).one()
    settings_row.roster_slots_json = {"QB": 2}
    db_session.add(settings_row)
    db_session.commit()

    duplicate_response = client.post(
        f"/teams/{team_id}/roster",
        json={"player_id": player_id, "slot": "QB", "status": "active"},
        headers=auth_headers(token),
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "player already on a league roster"
    assert db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"], RosterEntry.player_id == player_id).count() == 1
