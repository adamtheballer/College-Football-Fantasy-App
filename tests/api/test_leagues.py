from datetime import datetime, timedelta, timezone

from conftest import TestingSessionLocal
import pytest
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_invite import LeagueInvite
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings_version import LeagueSettingsVersion
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.league_schedule import ensure_league_schedule


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user_and_token(client, suffix: str = "one") -> str:
    email = f"coach-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={
            "first_name": f"Coach{suffix}",
            "email": email,
            "password": "StrongPass123!",
        },
    )
    assert response.status_code == 201
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == email).one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
    return response.json()["access_token"]


def create_unverified_user_and_token(client, suffix: str = "unverified") -> str:
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


def create_league(client, token: str, name: str = "Test League", max_teams: int = 12) -> dict:
    payload = {
        "basics": {
            "name": name,
            "season_year": 2026,
            "max_teams": max_teams,
            "is_private": True,
            "description": "Workspace league",
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1},
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
    }
    response = client.post(
        "/leagues",
        json=payload,
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def test_create_and_list_leagues(client):
    token = create_user_and_token(client)
    created = create_league(client, token)

    response = client.get("/leagues", headers=auth_headers(token))
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["data"][0]["name"] == created["name"]
    assert data["data"][0]["max_teams"] == created["max_teams"]
    assert len(data["data"][0]["members"]) == 1
    assert data["data"][0]["draft"]["draft_type"] == "snake"


def test_development_allows_unverified_user_to_create_league(client):
    token = create_unverified_user_and_token(client)
    created = create_league(client, token, name="Local Dev League")

    assert created["name"] == "Local Dev League"


def test_create_league_persists_custom_roster_format_and_flags(client):
    token = create_user_and_token(client, "custom-format")
    payload = {
        "basics": {
            "name": "Custom Format League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": True,
            "description": None,
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 0.5, "pass_td": 6},
            "roster_slots_json": {
                "QB": 1,
                "RB": 3,
                "WR": 2,
                "TE": 1,
                "FLEX": 2,
                "SUPERFLEX": 1,
                "K": 0,
                "BENCH": 7,
                "IR": 2,
            },
            "playoff_teams": 6,
            "waiver_type": "rolling",
            "trade_review_type": "league_vote",
            "superflex_enabled": True,
            "kicker_enabled": False,
            "defense_enabled": True,
        },
        "draft": {
            "draft_datetime_utc": "2026-08-19T18:00:00Z",
            "timezone": "America/Los_Angeles",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }

    response = client.post("/leagues", json=payload, headers=auth_headers(token))

    assert response.status_code == 201
    settings = response.json()["league"]["settings"]
    assert settings["roster_slots_json"] == {
        "QB": 1,
        "RB": 3,
        "WR": 2,
        "TE": 1,
        "FLEX": 2,
        "SUPERFLEX": 1,
        "K": 0,
        "BENCH": 7,
        "IR": 2,
    }
    assert settings["superflex_enabled"] is True
    assert settings["kicker_enabled"] is False
    assert settings["defense_enabled"] is True
    assert settings["playoff_teams"] == 6
    assert settings["waiver_type"] == "rolling"
    assert settings["trade_review_type"] == "league_vote"


def test_create_league_rejects_odd_manager_count(client):
    token = create_user_and_token(client, "odd-size")
    payload = {
        "basics": {
            "name": "Odd League",
            "season_year": 2026,
            "max_teams": 11,
            "is_private": True,
            "description": None,
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1},
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
    }

    response = client.post("/leagues", json=payload, headers=auth_headers(token))

    assert response.status_code == 422
    assert "even number" in str(response.json()["detail"])


def test_schedule_generation_rejects_legacy_odd_team_count(client, db_session):
    token = create_user_and_token(client, "legacy-odd")
    league = create_league(client, token, name="Legacy Odd League", max_teams=4)
    league_row = db_session.get(League, league["id"])
    db_session.flush()
    db_session.add_all(
        [
            Team(league_id=league_row.id, name="Legacy Team Two"),
            Team(league_id=league_row.id, name="Legacy Team Three"),
        ]
    )
    db_session.commit()

    with pytest.raises(ValueError, match="Even number of teams required"):
        ensure_league_schedule(db_session, league_row)


def test_create_invite_join_assigns_one_team_per_user_and_enforces_max_teams(client, db_session):
    owner_token = create_user_and_token(client, "invite-owner")
    member_token = create_user_and_token(client, "invite-member")
    third_token = create_user_and_token(client, "invite-third")

    create_response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": "Invite Capacity League",
                "season_year": 2026,
                "max_teams": 2,
                "is_private": True,
                "description": "Invite link league",
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 1},
                "playoff_teams": 2,
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
        headers=auth_headers(owner_token),
    )
    assert create_response.status_code == 201
    created = create_response.json()
    league = created["league"]
    invite_code = created["invite_code"]

    assert invite_code
    assert created["invite_link"].endswith(f"/join/{invite_code}")
    assert league["max_teams"] == 2
    assert len(league["members"]) == 1

    preview_response = client.post("/leagues/join-by-code", json={"invite_code": invite_code.lower()})
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["id"] == league["id"]
    assert preview["member_count"] == 1
    assert preview["max_teams"] == 2

    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200
    joined = join_response.json()
    assert len(joined["members"]) == 2

    duplicate_join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert duplicate_join_response.status_code == 200
    assert len(duplicate_join_response.json()["members"]) == 2

    full_join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(third_token))
    assert full_join_response.status_code == 409
    assert full_join_response.json()["detail"] == "league is full"

    owner = db_session.query(User).filter(User.email == "coach-invite-owner@example.com").one()
    member = db_session.query(User).filter(User.email == "coach-invite-member@example.com").one()
    third = db_session.query(User).filter(User.email == "coach-invite-third@example.com").one()
    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.owner_user_id.asc()).all()

    assert len(teams) == 2
    assert {team.owner_user_id for team in teams} == {owner.id, member.id}
    assert db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id == owner.id).count() == 1
    assert db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id == member.id).count() == 1
    assert db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id == third.id).count() == 0


def test_expired_invite_cannot_be_previewed_or_used(client, db_session):
    owner_token = create_user_and_token(client, "expired-invite-owner")
    member_token = create_user_and_token(client, "expired-invite-member")
    league = create_league(client, owner_token, name="Expired Invite League", max_teams=2)
    invite = db_session.query(LeagueInvite).filter(LeagueInvite.league_id == league["id"]).one()
    invite.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.add(invite)
    db_session.commit()

    preview_response = client.post("/leagues/join-by-code", json={"invite_code": invite.code})
    assert preview_response.status_code == 410
    assert preview_response.json()["detail"] == "invite code expired"

    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 410
    assert join_response.json()["detail"] == "invite code expired"


def test_update_league_settings_persists_custom_roster_format_and_flags(client):
    token = create_user_and_token(client, "update-format")
    league = create_league(client, token)
    payload = {
        "scoring_json": {"ppr": 1, "pass_td": 4},
        "roster_slots_json": {
            "QB": 1,
            "RB": 2,
            "WR": 4,
            "TE": 2,
            "FLEX": 1,
            "SUPERFLEX": 0,
            "K": 2,
            "BENCH": 8,
            "IR": 3,
        },
        "playoff_teams": 8,
        "waiver_type": "reverse",
        "trade_review_type": "none",
        "superflex_enabled": False,
        "kicker_enabled": True,
        "defense_enabled": False,
    }

    response = client.patch(f"/leagues/{league['id']}/settings", json=payload, headers=auth_headers(token))

    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["roster_slots_json"] == {
        "QB": 1,
        "RB": 2,
        "WR": 4,
        "TE": 2,
        "FLEX": 1,
        "SUPERFLEX": 0,
        "K": 2,
        "BENCH": 8,
        "IR": 3,
    }
    assert settings["superflex_enabled"] is False
    assert settings["kicker_enabled"] is True
    assert settings["defense_enabled"] is False
    assert settings["playoff_teams"] == 8


def test_league_creation_and_settings_update_create_settings_versions(client, db_session):
    token = create_user_and_token(client, "settings-version")
    league = create_league(client, token)

    initial_versions = (
        db_session.query(LeagueSettingsVersion)
        .filter(LeagueSettingsVersion.league_id == league["id"])
        .order_by(LeagueSettingsVersion.version.asc())
        .all()
    )
    assert [version.version for version in initial_versions] == [1]
    assert initial_versions[0].settings_json["scoring_json"] == {"ppr": 1}

    payload = {
        "scoring_json": {"ppr": 1, "pass_td": 6},
        "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 6, "IR": 1},
        "playoff_teams": 6,
        "waiver_type": "faab",
        "trade_review_type": "commissioner",
        "superflex_enabled": False,
        "kicker_enabled": True,
        "defense_enabled": False,
    }

    response = client.patch(f"/leagues/{league['id']}/settings", json=payload, headers=auth_headers(token))

    assert response.status_code == 200
    versions = (
        db_session.query(LeagueSettingsVersion)
        .filter(LeagueSettingsVersion.league_id == league["id"])
        .order_by(LeagueSettingsVersion.version.asc())
        .all()
    )
    assert [version.version for version in versions] == [1, 2]
    assert versions[1].settings_json["scoring_json"] == {"ppr": 1, "pass_td": 6}


def test_roster_size_change_is_rejected_after_draft_has_picks(client, db_session):
    token = create_user_and_token(client, "post-draft-settings")
    league = create_league(client, token)
    player = Player(name="Drafted QB", position="QB", school="Texas")
    db_session.add(player)
    db_session.flush()
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    db_session.add(
        DraftPick(
            draft_id=draft.id,
            team_id=team.id,
            player_id=player.id,
            made_by_user_id=team.owner_user_id,
            round_number=1,
            round_pick=1,
            overall_pick=1,
        )
    )
    db_session.commit()

    payload = {
        "scoring_json": {"ppr": 1},
        "roster_slots_json": {"QB": 2, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 5, "IR": 1},
        "playoff_teams": 4,
        "waiver_type": "faab",
        "trade_review_type": "commissioner",
        "superflex_enabled": False,
        "kicker_enabled": True,
        "defense_enabled": False,
    }

    response = client.patch(f"/leagues/{league['id']}/settings", json=payload, headers=auth_headers(token))

    assert response.status_code == 409
    assert response.json()["detail"] == "roster size cannot be changed after draft starts"


def test_legacy_create_alias_still_works(client):
    token = create_user_and_token(client)
    payload = {
        "basics": {
            "name": "Legacy League",
            "season_year": 2026,
            "max_teams": 12,
            "is_private": True,
            "description": None,
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1},
            "roster_slots_json": {"QB": 1},
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
    }
    response = client.post("/leagues/create", json=payload, headers=auth_headers(token))
    assert response.status_code == 201


def test_league_detail_requires_membership(client):
    owner_token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token)

    response = client.get(f"/leagues/{league['id']}", headers=auth_headers(outsider_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_league_members_requires_membership(client):
    owner_token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token)

    response = client.get(f"/leagues/{league['id']}/members", headers=auth_headers(outsider_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_delete_league_requires_commissioner(client):
    commissioner_token = create_user_and_token(client, "commissioner")
    member_token = create_user_and_token(client, "member")
    league = create_league(client, commissioner_token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    response = client.delete(f"/leagues/{league['id']}", headers=auth_headers(member_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "commissioner only"


def test_commissioner_can_transfer_commissioner_role(client, db_session):
    commissioner_token = create_user_and_token(client, "transfer-owner")
    member_token = create_user_and_token(client, "transfer-member")
    league = create_league(client, commissioner_token, max_teams=2)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200
    member = db_session.query(User).filter(User.email == "coach-transfer-member@example.com").one()

    response = client.post(
        f"/leagues/{league['id']}/commissioner",
        json={"user_id": member.id},
        headers=auth_headers(commissioner_token),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["commissioner_user_id"] == member.id
    roles = {
        row.user_id: row.role
        for row in db_session.query(LeagueMember).filter(LeagueMember.league_id == league["id"]).all()
    }
    assert roles[member.id] == "commissioner"


def test_commissioner_can_remove_member_before_draft_picks(client, db_session):
    commissioner_token = create_user_and_token(client, "remove-owner")
    member_token = create_user_and_token(client, "remove-member")
    league = create_league(client, commissioner_token, max_teams=4)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200
    member = db_session.query(User).filter(User.email == "coach-remove-member@example.com").one()

    response = client.delete(
        f"/leagues/{league['id']}/members/{member.id}",
        headers=auth_headers(commissioner_token),
    )

    assert response.status_code == 200
    assert db_session.query(LeagueMember).filter(LeagueMember.league_id == league["id"], LeagueMember.user_id == member.id).count() == 0
    assert db_session.query(Team).filter(Team.league_id == league["id"], Team.owner_user_id == member.id).count() == 0


def test_commissioner_can_reset_draft_before_completed_games(client, db_session):
    token = create_user_and_token(client, "reset-draft")
    league = create_league(client, token)
    player = Player(name="Reset Draft QB", position="QB", school="Texas")
    db_session.add(player)
    db_session.flush()
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    draft.status = "completed"
    db_session.add_all(
        [
            draft,
            DraftPick(
                draft_id=draft.id,
                team_id=team.id,
                player_id=player.id,
                made_by_user_id=team.owner_user_id,
                round_number=1,
                round_pick=1,
                overall_pick=1,
            ),
            RosterEntry(
                league_id=league["id"],
                team_id=team.id,
                player_id=player.id,
                slot="QB",
                status="active",
            ),
        ]
    )
    db_session.commit()

    response = client.post(f"/leagues/{league['id']}/reset-draft", headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["status"] == "draft_scheduled"
    db_session.refresh(draft)
    assert draft.status == "scheduled"
    assert db_session.query(DraftPick).filter(DraftPick.draft_id == draft.id).count() == 0
    assert db_session.query(RosterEntry).filter(RosterEntry.league_id == league["id"]).count() == 0


def test_league_with_completed_games_must_be_archived_not_deleted(client, db_session):
    token = create_user_and_token(client, "archive-required")
    member_token = create_user_and_token(client, "archive-member")
    league = create_league(client, token, max_teams=2)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200
    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    db_session.add(
        Matchup(
            league_id=league["id"],
            season=2026,
            week=1,
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            status="final",
            home_score=100.0,
            away_score=90.0,
        )
    )
    db_session.commit()

    delete_response = client.delete(f"/leagues/{league['id']}", headers=auth_headers(token))
    assert delete_response.status_code == 409
    assert delete_response.json()["detail"] == "league has completed games and must be archived instead of deleted"

    archive_response = client.post(f"/leagues/{league['id']}/archive", headers=auth_headers(token))
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"


def test_league_workspace_returns_real_matchup_and_standings(client, db_session):
    token = create_user_and_token(client, "workspace")
    member_token = create_user_and_token(client, "member")
    league = create_league(client, token)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    assert len(teams) == 2
    commissioner_team, member_team = teams

    db_session.add(
        Matchup(
            league_id=league["id"],
            season=2026,
            week=3,
            home_team_id=commissioner_team.id,
            away_team_id=member_team.id,
            status="live",
            home_score=118.4,
            away_score=111.2,
        )
    )
    db_session.add_all(
        [
            Standing(
                league_id=league["id"],
                team_id=commissioner_team.id,
                season=2026,
                week=3,
                wins=2,
                losses=0,
                ties=0,
                points_for=244.7,
                points_against=196.0,
            ),
            Standing(
                league_id=league["id"],
                team_id=member_team.id,
                season=2026,
                week=3,
                wins=1,
                losses=1,
                ties=0,
                points_for=210.3,
                points_against=211.8,
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        f"/leagues/{league['id']}/workspace",
        headers=auth_headers(token),
    )
    assert response.status_code == 200

    body = response.json()
    assert body["matchup_summary"]["week"] == 3
    assert body["matchup_summary"]["opponent_team_name"] == member_team.name
    assert body["matchup_summary"]["projected_points_for"] == 118.4
    assert body["standings_summary"][0]["team_id"] == commissioner_team.id
    assert body["standings_summary"][0]["wins"] == 2
    assert body["standings_summary"][1]["team_id"] == member_team.id


def test_league_workspace_requires_membership(client):
    owner_token = create_user_and_token(client, "owner")
    outsider_token = create_user_and_token(client, "outsider")
    league = create_league(client, owner_token)

    response = client.get(
        f"/leagues/{league['id']}/workspace",
        headers=auth_headers(outsider_token),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "league membership required"


def test_league_hub_endpoints_return_scoreboard_rankings_and_news(client, db_session):
    commissioner_token = create_user_and_token(client, "comm")
    member_token = create_user_and_token(client, "member")
    league = create_league(client, commissioner_token, name="Hub League")
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    commissioner_team, member_team = teams

    player = Player(name="Sam Test", position="QB", school="Alabama")
    db_session.add(player)
    db_session.flush()

    db_session.add(
        RosterEntry(
            league_id=league["id"],
            team_id=commissioner_team.id,
            player_id=player.id,
            slot="QB",
            status="active",
        )
    )
    db_session.add(
        Matchup(
            league_id=league["id"],
            season=2026,
            week=4,
            home_team_id=commissioner_team.id,
            away_team_id=member_team.id,
            status="live",
            home_score=128.5,
            away_score=120.1,
        )
    )
    db_session.add_all(
        [
            Standing(
                league_id=league["id"],
                team_id=commissioner_team.id,
                season=2026,
                week=4,
                wins=3,
                losses=0,
                ties=0,
                points_for=372.6,
                points_against=320.0,
            ),
            Standing(
                league_id=league["id"],
                team_id=member_team.id,
                season=2026,
                week=4,
                wins=1,
                losses=2,
                ties=0,
                points_for=298.4,
                points_against=325.7,
            ),
        ]
    )
    db_session.add(
        Transaction(
            league_id=league["id"],
            team_id=commissioner_team.id,
            transaction_type="add",
            player_id=player.id,
            created_by_user_id=league["commissioner_user_id"],
            reason="Waiver claim",
        )
    )
    db_session.add(
        Injury(
            player_id=player.id,
            season=2026,
            week=4,
            status="QUESTIONABLE",
            injury="Shoulder",
            return_timeline="Day-to-day",
        )
    )
    db_session.commit()

    matchup_response = client.get(
        f"/leagues/{league['id']}/matchups",
        headers=auth_headers(commissioner_token),
    )
    assert matchup_response.status_code == 200
    matchup_body = matchup_response.json()
    assert matchup_body["total"] == 1
    assert matchup_body["data"][0]["week"] == 4
    assert matchup_body["data"][0]["home_team_name"] == commissioner_team.name

    rankings_response = client.get(
        f"/leagues/{league['id']}/power-rankings",
        headers=auth_headers(commissioner_token),
    )
    assert rankings_response.status_code == 200
    rankings_body = rankings_response.json()
    assert rankings_body["total"] == 2
    assert rankings_body["data"][0]["team_id"] == commissioner_team.id
    assert rankings_body["data"][0]["rank"] == 1

    news_response = client.get(
        f"/leagues/{league['id']}/news",
        headers=auth_headers(commissioner_token),
    )
    assert news_response.status_code == 200
    news_body = news_response.json()
    assert news_body["total"] >= 2
    assert any(item["transaction_type"] == "add" for item in news_body["data"])
    assert any(item["transaction_type"] == "injury" for item in news_body["data"])


def test_league_hub_endpoints_require_membership(client):
    owner_token = create_user_and_token(client, "owner-hub")
    outsider_token = create_user_and_token(client, "outsider-hub")
    league = create_league(client, owner_token, name="Protected Hub League")

    for path in ("matchups", "power-rankings", "news"):
        response = client.get(f"/leagues/{league['id']}/{path}", headers=auth_headers(outsider_token))
        assert response.status_code == 403
        assert response.json()["detail"] == "league membership required"
