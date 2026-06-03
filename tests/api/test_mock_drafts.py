from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.api.routes import mock_drafts as mock_draft_routes
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.mock_draft_roster import MockDraftRosterEntry
from collegefootballfantasy_api.app.models.mock_draft_session import MockDraftSession
from collegefootballfantasy_api.app.models.mock_draft_timer_state import MockDraftTimerState
from collegefootballfantasy_api.app.models.player import Player


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": f"coach-mock-{suffix}@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def create_player_with_position(client, *, name: str, position: str, school: str = "Texas") -> int:
    response = client.post(
        "/players",
        json=[
            {
                "external_id": None,
                "name": name,
                "position": position,
                "school": school,
                "image_url": None,
            }
        ],
    )
    assert response.status_code == 201
    return response.json()[0]["id"]


def force_mock_draft_live(db_session, *, mock_draft_id: int) -> None:
    session_row = db_session.get(MockDraftSession, mock_draft_id)
    assert session_row is not None
    session_row.status = "live"
    timer_row = (
        db_session.query(MockDraftTimerState)
        .filter(MockDraftTimerState.session_id == mock_draft_id)
        .first()
    )
    assert timer_row is not None
    timer_row.timer_started_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    timer_row.paused_at = None
    timer_row.paused_total_seconds = 0
    db_session.add(session_row)
    db_session.add(timer_row)
    db_session.commit()


def expire_mock_seat_fill_timer(db_session, *, mock_draft_id: int) -> None:
    session_row = db_session.get(MockDraftSession, mock_draft_id)
    assert session_row is not None
    session_row.draft_datetime_utc = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.add(session_row)
    db_session.commit()


def test_create_mock_draft_isolated_from_leagues(client, db_session):
    token = create_user_and_token(client, "create")
    initial_league_count = db_session.query(League.id).count()

    response = client.post(
        "/mock-drafts",
        json={"manager_count": 4, "pick_timer_seconds": 60, "name": "Saturday Mock"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["manager_count"] == 4
    assert payload["invite_code"]
    assert len(payload["invite_code"]) == mock_draft_routes.MOCK_DRAFT_PUBLIC_INVITE_LENGTH
    assert payload["mode"] == "public_multiplayer"
    assert payload["status"] == "scheduled"
    assert payload["joined_count"] == 1
    assert payload["user_seat_id"] is not None
    assert payload["can_enter_room"] is False
    assert payload["seconds_remaining"] <= mock_draft_routes.MOCK_DRAFT_SEAT_FILL_SECONDS
    assert len(payload["seats"]) == 4
    assert db_session.query(League.id).count() == initial_league_count


def test_mock_draft_preview_and_join_reuses_existing_seat(client):
    commissioner_token = create_user_and_token(client, "preview-comm")
    member_token = create_user_and_token(client, "preview-member")

    create_response = client.post(
        "/mock-drafts",
        json={"manager_count": 4, "pick_timer_seconds": 90, "name": "Preview Mock"},
        headers=auth_headers(commissioner_token),
    )
    assert create_response.status_code == 200
    invite_code = create_response.json()["invite_code"]

    preview_response = client.post("/mock-drafts/join-by-code", json={"invite_code": invite_code})
    assert preview_response.status_code == 200
    assert preview_response.json()["invite_code"] == invite_code

    first_join = client.post(
        "/mock-drafts/join-with-code",
        json={"invite_code": invite_code},
        headers=auth_headers(member_token),
    )
    assert first_join.status_code == 200
    first_seat_id = first_join.json()["user_seat_id"]

    second_join = client.post(
        "/mock-drafts/join-with-code",
        json={"invite_code": invite_code},
        headers=auth_headers(member_token),
    )
    assert second_join.status_code == 200
    assert second_join.json()["user_seat_id"] == first_seat_id


def test_single_player_mock_draft_starts_with_cpu_managers(client):
    token = create_user_and_token(client, "single-player")

    create_response = client.post(
        "/mock-drafts",
        json={"manager_count": 4, "pick_timer_seconds": 90, "name": "Solo Mock", "mode": "single_player"},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["mode"] == "single_player"
    assert payload["status"] == "countdown"
    assert payload["can_enter_room"] is True
    assert payload["joined_count"] == 4
    assert sum(1 for seat in payload["seats"] if seat["is_cpu"]) == 3


def test_single_player_mock_draft_rejects_invite_preview_and_join(client):
    token = create_user_and_token(client, "single-player-code")

    create_response = client.post(
        "/mock-drafts",
        json={"manager_count": 4, "pick_timer_seconds": 90, "name": "Solo Mock", "mode": "single_player"},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 200
    invite_code = create_response.json()["invite_code"]

    preview_response = client.post("/mock-drafts/join-by-code", json={"invite_code": invite_code})
    assert preview_response.status_code == 409
    assert preview_response.json()["detail"] == "mock draft is not joinable by invite code"

    join_response = client.post(
        "/mock-drafts/join-with-code",
        json={"invite_code": invite_code},
        headers=auth_headers(create_user_and_token(client, "single-player-other")),
    )
    assert join_response.status_code == 409
    assert join_response.json()["detail"] == "mock draft is not joinable by invite code"


def test_mock_draft_rejects_join_when_full(client):
    tokens = [create_user_and_token(client, f"full-{index}") for index in range(5)]
    create_response = client.post(
        "/mock-drafts",
        json={"manager_count": 4, "pick_timer_seconds": 60, "name": "Full Mock"},
        headers=auth_headers(tokens[0]),
    )
    assert create_response.status_code == 200
    invite_code = create_response.json()["invite_code"]

    for token in tokens[1:4]:
        join_response = client.post(
            "/mock-drafts/join-with-code",
            json={"invite_code": invite_code},
            headers=auth_headers(token),
        )
        assert join_response.status_code == 200

    full_response = client.post(
        "/mock-drafts/join-with-code",
        json={"invite_code": invite_code},
        headers=auth_headers(tokens[4]),
    )
    assert full_response.status_code == 409
    assert full_response.json()["detail"] == "mock draft is full"


def test_mock_draft_seat_fill_expiry_converts_open_seats_to_cpu(client, db_session):
    commissioner_token = create_user_and_token(client, "start-comm")
    member_token = create_user_and_token(client, "start-member")
    create_response = client.post(
        "/mock-drafts",
        json={"manager_count": 4, "pick_timer_seconds": 90, "name": "Start Mock"},
        headers=auth_headers(commissioner_token),
    )
    assert create_response.status_code == 200
    mock_draft_id = create_response.json()["id"]
    invite_code = create_response.json()["invite_code"]

    join_response = client.post(
        "/mock-drafts/join-with-code",
        json={"invite_code": invite_code},
        headers=auth_headers(member_token),
    )
    assert join_response.status_code == 200

    expire_mock_seat_fill_timer(db_session, mock_draft_id=mock_draft_id)

    lobby_response = client.get(f"/mock-drafts/{mock_draft_id}/lobby", headers=auth_headers(commissioner_token))
    assert lobby_response.status_code == 200
    assert lobby_response.json()["status"] == "countdown"
    assert lobby_response.json()["can_enter_room"] is True
    assert lobby_response.json()["seconds_remaining"] <= mock_draft_routes.MOCK_DRAFT_ROOM_PREVIEW_SECONDS
    cpu_seats = [seat for seat in lobby_response.json()["seats"] if seat["is_cpu"]]
    assert len(cpu_seats) == 2


def test_mock_draft_join_is_closed_after_room_preview_unlocks(client, db_session):
    commissioner_token = create_user_and_token(client, "join-closed-comm")
    member_token = create_user_and_token(client, "join-closed-member")

    create_response = client.post(
        "/mock-drafts",
        json={"manager_count": 4, "pick_timer_seconds": 90, "name": "Closed Join Mock"},
        headers=auth_headers(commissioner_token),
    )
    assert create_response.status_code == 200
    mock_draft_id = create_response.json()["id"]
    invite_code = create_response.json()["invite_code"]

    expire_mock_seat_fill_timer(db_session, mock_draft_id=mock_draft_id)
    lobby_response = client.get(f"/mock-drafts/{mock_draft_id}/lobby", headers=auth_headers(commissioner_token))
    assert lobby_response.status_code == 200
    assert lobby_response.json()["status"] == "countdown"

    join_response = client.post(
        "/mock-drafts/join-with-code",
        json={"invite_code": invite_code},
        headers=auth_headers(member_token),
    )
    assert join_response.status_code == 409
    assert join_response.json()["detail"] == "mock draft is no longer joinable"


def test_mock_draft_pick_and_queue_do_not_touch_league_tables(client, db_session):
    token = create_user_and_token(client, "pick")
    rb_id = create_player_with_position(client, name="Mock RB 1", position="RB")
    qb_id = create_player_with_position(client, name="Mock QB 1", position="QB")

    create_response = client.post(
        "/mock-drafts",
        json={"manager_count": 4, "pick_timer_seconds": 90, "name": "Pick Mock"},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 200
    mock_draft_id = create_response.json()["id"]

    expire_mock_seat_fill_timer(db_session, mock_draft_id=mock_draft_id)
    lobby_response = client.get(f"/mock-drafts/{mock_draft_id}/lobby", headers=auth_headers(token))
    assert lobby_response.status_code == 200
    assert lobby_response.json()["status"] == "countdown"

    force_mock_draft_live(db_session, mock_draft_id=mock_draft_id)

    queue_response = client.post(
        f"/mock-drafts/{mock_draft_id}/queue",
        json={"player_id": qb_id},
        headers=auth_headers(token),
    )
    assert queue_response.status_code == 200
    assert queue_response.json()["count"] == 1

    pick_response = client.post(
        f"/mock-drafts/{mock_draft_id}/pick",
        json={"player_id": rb_id},
        headers=auth_headers(token),
    )
    assert pick_response.status_code == 200
    payload = pick_response.json()
    assert len(payload["picks"]) == 1
    assert payload["picks"][0]["player_id"] == rb_id

    roster_count = (
        db_session.query(MockDraftRosterEntry.id)
        .filter(MockDraftRosterEntry.session_id == mock_draft_id)
        .count()
    )
    assert roster_count == 1
    assert db_session.query(League.id).count() == 0
    assert db_session.query(Player.id).filter(Player.id.in_([rb_id, qb_id])).count() == 2


def test_mock_draft_delete_cascades_mock_data(client, db_session):
    token = create_user_and_token(client, "delete")
    create_response = client.post(
        "/mock-drafts",
        json={"manager_count": 4, "pick_timer_seconds": 90, "name": "Delete Mock"},
        headers=auth_headers(token),
    )
    assert create_response.status_code == 200
    mock_draft_id = create_response.json()["id"]

    delete_response = client.delete(f"/mock-drafts/{mock_draft_id}", headers=auth_headers(token))
    assert delete_response.status_code == 204
    assert db_session.get(MockDraftSession, mock_draft_id) is None
