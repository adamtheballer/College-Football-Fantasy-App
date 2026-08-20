from datetime import datetime, timedelta, timezone

from conftest import TestingSessionLocal
from tests.api.test_leagues import auth_headers, create_league, create_user_and_token

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league_rivalry import LeagueRivalryBinding, LeagueRivalryInvite
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.team import Team


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


def test_only_the_final_scheduled_rival_meeting_gets_rival_week_context(client):
    league, sender_token, recipient_token = _completed_two_manager_league(client)
    candidate = client.get(f"/leagues/{league['id']}/rivalry", headers=auth_headers(recipient_token)).json()["candidates"][0]
    invite = client.post(
        f"/leagues/{league['id']}/rivalry/invites",
        json={"recipient_team_id": candidate["team_id"]},
        headers=auth_headers(recipient_token),
    ).json()
    assert client.post(
        f"/leagues/{league['id']}/rivalry/invites/{invite['id']}/accept",
        headers=auth_headers(sender_token),
    ).status_code == 200

    with TestingSessionLocal() as db:
        teams = db.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
        db.add_all(
            [
                Matchup(league_id=league["id"], season=2026, week=2, home_team_id=teams[0].id, away_team_id=teams[1].id, status="projected"),
                Matchup(league_id=league["id"], season=2026, week=12, home_team_id=teams[1].id, away_team_id=teams[0].id, status="projected"),
            ]
        )
        db.commit()

    first_meeting = client.get(f"/leagues/{league['id']}/matchup?week=2", headers=auth_headers(sender_token))
    assert first_meeting.status_code == 200
    assert first_meeting.json()["rivalry"] is None

    final_meeting = client.get(f"/leagues/{league['id']}/matchup?week=12", headers=auth_headers(sender_token))
    assert final_meeting.status_code == 200
    assert final_meeting.json()["rivalry"]["is_rivalry_matchup"] is True
