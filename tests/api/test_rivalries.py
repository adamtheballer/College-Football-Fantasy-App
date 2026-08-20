from datetime import datetime, timedelta, timezone

from conftest import TestingSessionLocal
from tests.api.test_leagues import auth_headers, create_league, create_user_and_token

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league_rivalry import LeagueRivalryBinding, LeagueRivalryInvite


def _completed_two_manager_league(client):
    sender_token = create_user_and_token(client, "rival-sender")
    recipient_token = create_user_and_token(client, "rival-recipient")
    league = create_league(client, sender_token, name="Rival League", max_teams=2)
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(recipient_token)).status_code == 200
    with TestingSessionLocal() as db:
        draft = db.query(Draft).filter(Draft.league_id == league["id"]).one()
        draft.status = "completed"
        db.commit()
    return league, sender_token, recipient_token


def test_rivalry_invitation_becomes_one_mutual_permanent_binding(client):
    league, sender_token, recipient_token = _completed_two_manager_league(client)
    recipient_view = client.get(f"/leagues/{league['id']}/rivalry", headers=auth_headers(recipient_token))
    assert recipient_view.status_code == 200
    candidate = recipient_view.json()["candidates"][0]
    invite = client.post(f"/leagues/{league['id']}/rivalry/invites", json={"recipient_team_id": candidate["team_id"]}, headers=auth_headers(recipient_token))
    assert invite.status_code == 201
    invitation = invite.json()
    accepted = client.post(f"/leagues/{league['id']}/rivalry/invites/{invitation['id']}/accept", headers=auth_headers(sender_token))
    assert accepted.status_code == 200
    assert accepted.json()["rivalry"]["status"] == "ACTIVE"
    with TestingSessionLocal() as db:
        assert db.query(LeagueRivalryBinding).filter(LeagueRivalryBinding.league_id == league["id"]).count() == 2
        assert db.query(LeagueRivalryInvite).filter(LeagueRivalryInvite.id == invitation["id"]).one().status == "ACCEPTED"
    second_attempt = client.post(f"/leagues/{league['id']}/rivalry/invites", json={"recipient_team_id": candidate["team_id"]}, headers=auth_headers(recipient_token))
    assert second_attempt.status_code == 409


def test_rivalry_invites_require_completed_draft_and_expire_lazily(client):
    sender_token = create_user_and_token(client, "rival-lock-sender")
    recipient_token = create_user_and_token(client, "rival-lock-recipient")
    league = create_league(client, sender_token, name="Locked Rival League", max_teams=2)
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(recipient_token)).status_code == 200
    candidate = client.get(f"/leagues/{league['id']}/rivalry", headers=auth_headers(sender_token)).json()["candidates"]
    assert candidate == []
    with TestingSessionLocal() as db:
        draft = db.query(Draft).filter(Draft.league_id == league["id"]).one(); draft.status = "completed"; db.commit()
    candidate = client.get(f"/leagues/{league['id']}/rivalry", headers=auth_headers(sender_token)).json()["candidates"][0]
    invite = client.post(f"/leagues/{league['id']}/rivalry/invites", json={"recipient_team_id": candidate["team_id"]}, headers=auth_headers(sender_token)).json()
    with TestingSessionLocal() as db:
        row = db.get(LeagueRivalryInvite, invite["id"]); row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
    view = client.get(f"/leagues/{league['id']}/rivalry", headers=auth_headers(sender_token))
    assert view.status_code == 200 and view.json()["outgoing_invite"] is None
