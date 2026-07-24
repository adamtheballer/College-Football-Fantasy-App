from datetime import datetime, timedelta, timezone

from conftest import TestingSessionLocal
import pytest
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_invite import LeagueInvite
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.league_schedule import ensure_league_schedule
from collegefootballfantasy_api.app.services.scoring_service import normalize_scoring_rules


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


def test_scoring_rules_normalize_create_form_aliases():
    rules = normalize_scoring_rules(
        {
            "ppr": 1,
            "pass_td": 4,
            "pass_yds_per_pt": 25,
            "rush_yds_per_pt": 10,
            "rec_yds_per_pt": 10,
            "rush_td": 6,
            "rec_td": 6,
            "int": -2,
            "fumble_lost": -2,
            "fg": 3,
            "xp": 1,
        }
    )

    assert rules["receptions"] == 1
    assert rules["pass_tds"] == 4
    assert rules["pass_yards"] == pytest.approx(0.04)
    assert rules["rush_yards"] == pytest.approx(0.1)
    assert rules["rec_yards"] == pytest.approx(0.1)
    assert rules["rush_tds"] == 6
    assert rules["rec_tds"] == 6
    assert rules["interceptions"] == -2
    assert rules["fumbles_lost"] == -2
    assert rules["fg_made_0_39"] == 3
    assert rules["xp_made"] == 1


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
            "waiver_type": "priority",
            "trade_review_type": "commissioner",
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
    assert settings["waiver_type"] == "priority"
    assert settings["trade_review_type"] == "commissioner"


def test_create_league_accepts_create_form_scoring_keys(client):
    token = create_user_and_token(client, "create-form-scoring")
    payload = {
        "basics": {
            "name": "Create Form Scoring League",
            "season_year": 2026,
            "max_teams": 4,
            "is_private": True,
            "description": None,
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {
                "ppr": 1,
                "pass_td": 4,
                "pass_yds_per_pt": 25,
                "rush_yds_per_pt": 10,
                "rec_yds_per_pt": 10,
                "rush_td": 6,
                "rec_td": 6,
                "int": -2,
                "fumble_lost": -2,
                "fg": 3,
                "xp": 1,
            },
            "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 5},
            "playoff_teams": 4,
            "waiver_type": "faab",
            "trade_review_type": "commissioner",
            "superflex_enabled": False,
            "kicker_enabled": True,
            "defense_enabled": False,
        },
        "draft": {
            "draft_datetime_utc": "2026-08-19T18:00:00Z",
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }

    response = client.post("/leagues", json=payload, headers=auth_headers(token))

    assert response.status_code == 201
    scoring = response.json()["league"]["settings"]["scoring_json"]
    assert scoring["receptions"] == 1
    assert scoring["pass_tds"] == 4
    assert scoring["pass_yards"] == pytest.approx(0.04)
    assert scoring["rush_yards"] == pytest.approx(0.1)
    assert scoring["rec_yards"] == pytest.approx(0.1)
    assert scoring["rush_tds"] == 6
    assert scoring["rec_tds"] == 6
    assert scoring["interceptions"] == -2
    assert scoring["fumbles_lost"] == -2
    assert scoring["fg_made_0_39"] == 3
    assert scoring["xp_made"] == 1
    assert "pass_yds_per_pt" not in scoring
    assert "rush_yds_per_pt" not in scoring
    assert "rec_yds_per_pt" not in scoring


def test_create_league_rejects_unknown_scoring_keys(client):
    token = create_user_and_token(client, "bad-scoring")
    payload = {
        "basics": {
            "name": "Bad Scoring League",
            "season_year": 2026,
            "max_teams": 4,
            "is_private": True,
            "description": None,
            "icon_url": None,
        },
        "settings": {
            "scoring_json": {"ppr": 1, "passing_bonus": 3},
            "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 5},
            "playoff_teams": 4,
            "waiver_type": "faab",
            "trade_review_type": "commissioner",
            "superflex_enabled": False,
            "kicker_enabled": True,
            "defense_enabled": False,
        },
        "draft": {
            "draft_datetime_utc": "2026-08-19T18:00:00Z",
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
    }

    response = client.post("/leagues", json=payload, headers=auth_headers(token))

    assert response.status_code == 422
    assert "unknown scoring keys" in response.json()["detail"]
    assert "passing_bonus" in response.json()["detail"]


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


def test_commissioner_settings_show_active_invite_until_draft_completion(client, db_session):
    owner_token = create_user_and_token(client, "settings-invite-owner")
    create_response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": "Settings Invite League",
                "season_year": 2026,
                "max_teams": 4,
                "is_private": True,
                "description": "Invite settings league",
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
                "timezone": "America/New_York",
                "draft_type": "snake",
                "pick_timer_seconds": 90,
            },
        },
        headers=auth_headers(owner_token),
    )
    assert create_response.status_code == 201
    created = create_response.json()
    league_id = created["league"]["id"]
    invite_code = created["invite_code"]

    league_row = db_session.get(League, league_id)
    assert league_row is not None
    league_row.invite_code = None
    db_session.commit()
    assert db_session.query(LeagueInvite).filter(LeagueInvite.league_id == league_id, LeagueInvite.code == invite_code).count() == 1

    settings_response = client.get(f"/leagues/{league_id}/settings-view", headers=auth_headers(owner_token))
    assert settings_response.status_code == 200
    invite = settings_response.json()["invite"]
    assert invite["code"] == invite_code
    assert invite["link"].endswith(f"/join/{invite_code}")
    assert invite["visible_until_draft_complete"] is True


def test_commissioner_can_rotate_and_revoke_invite(client, db_session):
    commissioner_token = create_user_and_token(client, "rotate-invite-commissioner")
    member_token = create_user_and_token(client, "rotate-invite-member")
    league = create_league(client, commissioner_token, name="Invite Lifecycle League", max_teams=4)
    original_code = league["invite_code"]

    joined = client.post(
        f"/leagues/{league['id']}/join",
        headers=auth_headers(member_token),
    )
    assert joined.status_code == 200

    commissioner_detail = client.get(
        f"/leagues/{league['id']}",
        headers=auth_headers(commissioner_token),
    )
    member_detail = client.get(
        f"/leagues/{league['id']}",
        headers=auth_headers(member_token),
    )
    assert commissioner_detail.status_code == 200
    assert commissioner_detail.json()["invite_code"] == original_code
    assert member_detail.status_code == 200
    assert member_detail.json()["invite_code"] is None

    unauthorized = client.post(
        f"/leagues/{league['id']}/invite/rotate",
        headers=auth_headers(member_token),
    )
    assert unauthorized.status_code == 403

    rotated = client.post(
        f"/leagues/{league['id']}/invite/rotate",
        headers=auth_headers(commissioner_token),
    )
    assert rotated.status_code == 200
    new_code = rotated.json()["invite_code"]
    assert new_code and new_code != original_code
    assert client.post("/leagues/join-by-code", json={"invite_code": original_code}).status_code == 404
    assert client.post("/leagues/join-by-code", json={"invite_code": new_code}).status_code == 200

    revoked = client.post(
        f"/leagues/{league['id']}/invite/revoke",
        headers=auth_headers(commissioner_token),
    )
    assert revoked.status_code == 200
    assert revoked.json()["invite_code"] is None
    assert client.post("/leagues/join-by-code", json={"invite_code": new_code}).status_code == 404
    db_session.expire_all()
    assert db_session.query(LeagueInvite).filter(LeagueInvite.code == new_code, LeagueInvite.active.is_(True)).count() == 0


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
        "waiver_type": "priority",
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
    assert settings["waiver_period_hours"] == 24
    assert settings["kicker_enabled"] is True
    assert settings["defense_enabled"] is False
    assert settings["playoff_teams"] == 8


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


def test_commissioner_can_reschedule_future_draft(client):
    token = create_user_and_token(client, "reschedule-commissioner")
    league = create_league(client, token, "Commissioner Reschedule")
    next_time = (datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=3)).isoformat()

    response = client.patch(
        f"/leagues/{league['id']}/draft",
        json={
            "draft_datetime_utc": next_time,
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 120,
            "status": "scheduled",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["pick_timer_seconds"] == 120
    assert response.json()["draft_datetime_utc"].startswith(next_time[:19])


def test_non_commissioner_cannot_reschedule_draft(client):
    commissioner_token = create_user_and_token(client, "reschedule-owner")
    member_token = create_user_and_token(client, "reschedule-member")
    league = create_league(client, commissioner_token, "Member Reschedule", max_teams=2)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    response = client.patch(
        f"/leagues/{league['id']}/draft",
        json={
            "draft_datetime_utc": (datetime.now(timezone.utc) + timedelta(days=4)).isoformat(),
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 120,
            "status": "scheduled",
        },
        headers=auth_headers(member_token),
    )

    assert response.status_code == 403


def test_started_draft_cannot_be_rescheduled(client, db_session):
    token = create_user_and_token(client, "reschedule-started")
    league = create_league(client, token, "Started Reschedule")
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    draft.status = "in_progress"
    db_session.commit()

    response = client.patch(
        f"/leagues/{league['id']}/draft",
        json={
            "draft_datetime_utc": (datetime.now(timezone.utc) + timedelta(days=4)).isoformat(),
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 120,
            "status": "scheduled",
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 409
    assert "cannot be rescheduled" in response.json()["detail"]
