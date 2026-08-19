from datetime import datetime, timedelta, timezone

from conftest import TestingSessionLocal
import pytest
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_invite import LeagueInvite
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGamePoll
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scheduled_notification import ScheduledNotification
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.trade_offer_item import TradeOfferItem
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.league_schedule import REGULAR_SEASON_WEEKS, ensure_league_schedule
from collegefootballfantasy_api.app.services.scoring_service import normalize_scoring_rules
from collegefootballfantasy_api.app.services.draft_service import process_expired_draft_picks_once
from collegefootballfantasy_api.app.core.config import settings


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


def test_beta_scoring_requires_acknowledgment_locks_snapshot_and_enforces_flat_kicker_policy(client, monkeypatch):
    monkeypatch.setattr(settings, "beta_scoring_lock_enabled", True)
    token = create_user_and_token(client, "beta-scoring-lock")
    payload = {
        "basics": {"name": "Beta Scoring Lock", "season_year": 2026, "max_teams": 4, "is_private": True},
        "settings": {
            "scoring_json": {"ppr": 1, "fg": 9, "xp": 4},
            "roster_slots_json": {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "FLEX": 1, "K": 1, "BENCH": 5},
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
    }
    denied = client.post("/leagues", json=payload, headers=auth_headers(token))
    assert denied.status_code == 422

    payload["beta_scoring_acknowledged"] = True
    created = client.post("/leagues", json=payload, headers=auth_headers(token))
    assert created.status_code == 201
    league = created.json()["league"]
    expected_beta_kicker_rules = {
        "fg_made_0_30": 3,
        "fg_made_31_40": 3,
        "fg_made_41_50": 4,
        "fg_made_51_60": 5,
        "fg_made_61_plus": 5,
        "xp_made": 1,
        "fg_missed": 0,
    }
    assert league["settings"]["scoring_snapshot_json"] == {"receptions": 1, **expected_beta_kicker_rules}
    assert league["settings"]["scoring_json"] == {"receptions": 1, **expected_beta_kicker_rules}
    assert league["settings"]["scoring_locked_at"] is not None

    update = {**payload["settings"], "scoring_json": {"ppr": 0.5}}
    rejected = client.patch(f"/leagues/{league['id']}/settings", json=update, headers=auth_headers(token))
    assert rejected.status_code == 409
    assert "locked" in rejected.json()["detail"]


def test_settings_trade_history_shows_completed_trade_parties_assets_and_time(client, db_session):
    owner_token = create_user_and_token(client, "settings-trade-owner")
    member_token = create_user_and_token(client, "settings-trade-member")
    league = create_league(client, owner_token, name="Settings Trade History", max_teams=2)
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token)).status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    outgoing = Player(name="Trade History QB", position="QB", school="Alpha")
    incoming = Player(name="Trade History RB", position="RB", school="Bravo")
    db_session.add_all([outgoing, incoming])
    db_session.flush()
    completed_at = datetime.now(timezone.utc)
    offer = TradeOffer(
        league_id=league["id"],
        proposing_team_id=teams[0].id,
        receiving_team_id=teams[1].id,
        status="processed",
        accepted_at=completed_at,
        processed_at=completed_at,
    )
    db_session.add(offer)
    db_session.flush()
    db_session.add_all([
        TradeOfferItem(trade_offer_id=offer.id, team_id=teams[0].id, player_id=outgoing.id, item_type="player"),
        TradeOfferItem(trade_offer_id=offer.id, team_id=teams[1].id, player_id=incoming.id, item_type="player"),
    ])
    db_session.commit()

    response = client.get(f"/leagues/{league['id']}/settings-view", headers=auth_headers(owner_token))

    assert response.status_code == 200
    history = response.json()["trade_history"]
    assert len(history) == 1
    assert history[0]["id"] == offer.id
    assert history[0]["proposing_party"]["team_name"] == teams[0].name
    assert history[0]["receiving_party"]["team_name"] == teams[1].name
    assert history[0]["proposing_team_sends"] == [{"player_id": outgoing.id, "name": "Trade History QB", "position": "QB", "school": "Alpha"}]
    assert history[0]["receiving_team_sends"] == [{"player_id": incoming.id, "name": "Trade History RB", "position": "RB", "school": "Bravo"}]
    assert history[0]["processed_at"] is not None


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
    assert rules["fg_made_0_30"] == 3
    assert rules["fg_made_31_40"] == 3
    assert rules["fg_made_41_50"] == 4
    assert rules["fg_made_51_60"] == 5
    assert rules["fg_made_61_plus"] == 5
    assert rules["xp_made"] == 1
    assert rules["fg_missed"] == 0


def test_create_league_enforces_standard_beta_roster_and_managed_processing(client):
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
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "FLEX": 1,
        "SUPERFLEX": 0,
        "K": 1,
        "BENCH": 5,
        "IR": 1,
    }
    assert settings["superflex_enabled"] is False
    assert settings["kicker_enabled"] is True
    assert settings["defense_enabled"] is False
    assert settings["playoff_teams"] == 6
    assert settings["waiver_type"] == "priority"
    assert settings["trade_review_type"] == "commissioner"
    assert settings["waiver_period_hours"] == 24
    assert settings["waiver_processing_weekday"] == 1
    assert settings["waiver_processing_hour"] == 8
    assert settings["waiver_timezone"] == "America/New_York"
    assert settings["faab_starting_budget"] == 100
    assert settings["allow_zero_faab_bids"] is True
    assert settings["reveal_all_waiver_bids"] is False
    assert settings["post_drop_waiver_hours"] == 24


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
    assert scoring["fg_made_0_30"] == 3
    assert scoring["fg_made_31_40"] == 3
    assert scoring["fg_made_41_50"] == 4
    assert scoring["fg_made_51_60"] == 5
    assert scoring["fg_made_61_plus"] == 5
    assert scoring["xp_made"] == 1
    assert scoring["fg_missed"] == 0
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


def test_schedule_generation_creates_and_backfills_a_fair_13_week_regular_season(client, db_session):
    token = create_user_and_token(client, "schedule-fairness")
    league = create_league(client, token, name="Fair Schedule League", max_teams=4)
    league_row = db_session.get(League, league["id"])
    assert league_row is not None
    db_session.add_all(
        [
            Team(league_id=league_row.id, name="Team Two"),
            Team(league_id=league_row.id, name="Team Three"),
            Team(league_id=league_row.id, name="Team Four"),
        ]
    )
    db_session.commit()

    teams = db_session.query(Team).filter(Team.league_id == league_row.id).order_by(Team.id.asc()).all()
    team_ids = {team.id for team in teams}
    assert len(team_ids) == 4

    assert ensure_league_schedule(db_session, league_row, regular_season_weeks=12) == 24
    assert ensure_league_schedule(db_session, league_row) == 2
    db_session.flush()

    matchups = (
        db_session.query(Matchup)
        .filter(Matchup.league_id == league_row.id, Matchup.season == league_row.season_year)
        .order_by(Matchup.week.asc(), Matchup.id.asc())
        .all()
    )
    assert len(matchups) == (len(team_ids) // 2) * REGULAR_SEASON_WEEKS
    assert {matchup.week for matchup in matchups} == set(range(1, REGULAR_SEASON_WEEKS + 1))

    matchup_counts_by_pair: dict[tuple[int, int], int] = {}
    for week in range(1, REGULAR_SEASON_WEEKS + 1):
        weekly_matchups = [matchup for matchup in matchups if matchup.week == week]
        assert len(weekly_matchups) == len(team_ids) // 2
        assert {team_id for matchup in weekly_matchups for team_id in (matchup.home_team_id, matchup.away_team_id)} == team_ids
        for matchup in weekly_matchups:
            pair = tuple(sorted((matchup.home_team_id, matchup.away_team_id)))
            matchup_counts_by_pair[pair] = matchup_counts_by_pair.get(pair, 0) + 1

    assert len(matchup_counts_by_pair) == 6
    assert max(matchup_counts_by_pair.values()) - min(matchup_counts_by_pair.values()) <= 1


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


def test_settings_view_shows_every_team_at_zero_zero_before_scoring(client, db_session):
    owner_token = create_user_and_token(client, "standings-owner")
    member_token = create_user_and_token(client, "standings-member")
    league = create_league(client, owner_token, name="Preseason Standings League", max_teams=2)

    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = (
        db_session.query(Team)
        .filter(Team.league_id == league["id"])
        .order_by(Team.id.asc())
        .all()
    )
    assert len(teams) == 2

    settings_response = client.get(f"/leagues/{league['id']}/settings-view", headers=auth_headers(owner_token))
    assert settings_response.status_code == 200
    payload = settings_response.json()

    assert payload["teams"] == [
        {
            "id": team.id,
            "league_id": league["id"],
            "name": team.name,
            "owner_user_id": team.owner_user_id,
        }
        for team in teams
    ]
    assert {
        (row["team_id"], row["wins"], row["losses"], row["ties"])
        for row in payload["standings"]
    } == {(team.id, 0, 0, 0) for team in teams}


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
    owner_player = Player(name="Workspace Owner QB", position="QB", school="Alabama")
    member_player = Player(name="Workspace Member QB", position="QB", school="Georgia")
    db_session.add_all([owner_player, member_player])
    db_session.flush()
    db_session.add_all(
        [
            RosterEntry(
                league_id=league["id"],
                team_id=commissioner_team.id,
                player_id=owner_player.id,
                slot="QB",
                status="active",
            ),
            RosterEntry(
                league_id=league["id"],
                team_id=member_team.id,
                player_id=member_player.id,
                slot="QB",
                status="active",
            ),
            WeeklyProjection(player_id=owner_player.id, season=2026, week=3, fantasy_points=133.1),
            WeeklyProjection(player_id=member_player.id, season=2026, week=3, fantasy_points=137.0),
        ]
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
    assert body["matchup_summary"]["projected_points_for"] == 133.1
    assert body["matchup_summary"]["projected_points_against"] == 137.0
    assert body["matchup_summary"]["win_probability_for"] == 48.05
    assert body["matchup_summary"]["win_probability_against"] == 51.95
    assert body["standings_summary"][0]["team_id"] == commissioner_team.id
    assert body["standings_summary"][0]["wins"] == 2
    assert body["standings_summary"][1]["team_id"] == member_team.id

    list_response = client.get("/leagues", headers=auth_headers(token))
    assert list_response.status_code == 200
    card_summary = list_response.json()["data"][0]["current_user_summary"]
    assert card_summary["team_name"] == commissioner_team.name
    assert card_summary["wins"] == 2
    assert card_summary["losses"] == 0
    assert card_summary["opponent_team_name"] == member_team.name
    assert card_summary["matchup_week"] == 3
    assert card_summary["projected_points_for"] == 133.1
    assert card_summary["projected_points_against"] == 137.0
    assert card_summary["win_probability_for"] == 48.05


def test_member_can_load_another_same_league_matchup_for_selected_week(client, db_session):
    commissioner_token = create_user_and_token(client, "matchup-selector-commissioner")
    league = create_league(client, commissioner_token, name="Matchup Selector League", max_teams=4)
    for suffix in ("matchup-selector-two", "matchup-selector-three", "matchup-selector-four"):
        member_token = create_user_and_token(client, suffix)
        assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token)).status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    assert len(teams) == 4
    own_matchup = Matchup(
        league_id=league["id"],
        season=2026,
        week=5,
        home_team_id=teams[0].id,
        away_team_id=teams[1].id,
        status="projected",
    )
    league_mate_matchup = Matchup(
        league_id=league["id"],
        season=2026,
        week=5,
        home_team_id=teams[2].id,
        away_team_id=teams[3].id,
        status="projected",
    )
    db_session.add_all([own_matchup, league_mate_matchup])
    db_session.commit()

    selected = client.get(
        f"/leagues/{league['id']}/matchup?week=5&matchup_id={league_mate_matchup.id}",
        headers=auth_headers(commissioner_token),
    )

    assert selected.status_code == 200
    body = selected.json()
    assert body["matchup_id"] == league_mate_matchup.id
    assert body["week"] == 5
    assert body["my_team"]["fantasy_team_id"] == teams[2].id
    assert body["opponent_team"]["fantasy_team_id"] == teams[3].id
    assert body["user_team"] is None

    wrong_week = client.get(
        f"/leagues/{league['id']}/matchup?week=6&matchup_id={league_mate_matchup.id}",
        headers=auth_headers(commissioner_token),
    )
    assert wrong_week.status_code == 404

    other_league = create_league(client, commissioner_token, name="Other Matchup Selector League", max_teams=2)
    other_member_token = create_user_and_token(client, "other-matchup-selector-member")
    assert client.post(
        f"/leagues/{other_league['id']}/join",
        headers=auth_headers(other_member_token),
    ).status_code == 200
    other_teams = db_session.query(Team).filter(Team.league_id == other_league["id"]).all()
    other_matchup = Matchup(
        league_id=other_league["id"],
        season=2026,
        week=5,
        home_team_id=other_teams[0].id,
        away_team_id=other_teams[1].id,
        status="projected",
    )
    db_session.add(other_matchup)
    db_session.commit()

    cross_league = client.get(
        f"/leagues/{league['id']}/matchup?week=5&matchup_id={other_matchup.id}",
        headers=auth_headers(commissioner_token),
    )
    assert cross_league.status_code == 404


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


def test_league_roster_tab_includes_every_team_current_roster(client, db_session):
    owner_token = create_user_and_token(client, "all-rosters-owner")
    member_token = create_user_and_token(client, "all-rosters-member")
    league = create_league(client, owner_token, name="All Rosters League", max_teams=2)
    join_response = client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token))
    assert join_response.status_code == 200

    teams = db_session.query(Team).filter(Team.league_id == league["id"]).order_by(Team.id.asc()).all()
    assert len(teams) == 2
    owner_team, member_team = teams
    owner_player = Player(name="Owner Quarterback", position="QB", school="Alabama")
    member_player = Player(name="Member Quarterback", position="QB", school="Georgia")
    db_session.add_all([owner_player, member_player])
    db_session.flush()
    db_session.add_all(
        [
            RosterEntry(
                league_id=league["id"],
                team_id=owner_team.id,
                player_id=owner_player.id,
                slot="QB",
                status="active",
            ),
            RosterEntry(
                league_id=league["id"],
                team_id=member_team.id,
                player_id=member_player.id,
                slot="QB",
                status="active",
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/leagues/{league['id']}/roster?week=1", headers=auth_headers(owner_token))
    assert response.status_code == 200
    body = response.json()

    assert [team_roster["team"]["id"] for team_roster in body["team_rosters"]] == [owner_team.id, member_team.id]
    assert [
        player["player_name"]
        for player in next(team_roster for team_roster in body["team_rosters"] if team_roster["team"]["id"] == owner_team.id)["roster"]
        if player["player_id"] is not None
    ] == ["Owner Quarterback"]
    assert [
        player["player_name"]
        for player in next(team_roster for team_roster in body["team_rosters"] if team_roster["team"]["id"] == member_team.id)["roster"]
        if player["player_id"] is not None
    ] == ["Member Quarterback"]


def test_league_roster_tab_uses_cached_espn_possession_and_red_zone_context(client, db_session):
    owner_token = create_user_and_token(client, "live-roster-owner")
    league = create_league(client, owner_token, name="Live Roster League")
    owner_team = db_session.query(Team).filter(Team.league_id == league["id"]).one()
    player = Player(name="Live Texas Quarterback", position="QB", school="Texas")
    db_session.add(player)
    db_session.flush()
    db_session.add(
        RosterEntry(
            league_id=league["id"],
            team_id=owner_team.id,
            player_id=player.id,
            slot="QB",
            status="active",
        )
    )
    db_session.add(
        Game(
            external_id="401-test-live",
            season=2026,
            week=1,
            home_team="Texas",
            away_team="Ohio State",
            start_date=datetime(2026, 8, 29, 16, tzinfo=timezone.utc),
            schedule_status="in_progress",
        )
    )
    db_session.add(
        ProviderGamePoll(
            provider="espn",
            provider_game_id="401-test-live",
            season=2026,
            week=1,
            status="live",
            accepted_snapshot_hash="accepted-summary",
            latest_payload={
                "header": {
                    "competitions": [
                        {
                            "status": {"type": {"state": "in", "completed": False}},
                            "competitors": [
                                {
                                    "id": "10",
                                    "team": {"id": "10", "location": "Texas", "displayName": "Texas Longhorns"},
                                },
                                {
                                    "id": "20",
                                    "team": {"id": "20", "location": "Ohio State", "displayName": "Ohio State Buckeyes"},
                                },
                            ],
                        }
                    ]
                },
                "situation": {"possession": "10", "isRedZone": True},
            },
        )
    )
    db_session.commit()

    response = client.get(f"/leagues/{league['id']}/roster?week=1", headers=auth_headers(owner_token))

    assert response.status_code == 200
    roster_player = next(row for row in response.json()["roster"] if row["player_id"] == player.id)
    assert roster_player["live_game_state"] == "live"
    assert roster_player["team_has_possession"] is True
    assert roster_player["team_in_red_zone"] is True


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

    for path in ("matchup", "matchups", "power-rankings", "news"):
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


def test_reschedule_persists_utc_time_replaces_notifications_and_records_member_event(client, db_session):
    commissioner_token = create_user_and_token(client, "reschedule-persist-owner")
    member_token = create_user_and_token(client, "reschedule-persist-member")
    league = create_league(client, commissioner_token, "Persisted Reschedule", max_teams=2)
    assert client.post(f"/leagues/{league['id']}/join", headers=auth_headers(member_token)).status_code == 200
    before = (
        db_session.query(ScheduledNotification)
        .filter(ScheduledNotification.league_id == league["id"], ScheduledNotification.canceled_at.is_(None))
        .all()
    )
    # One durable one-hour reminder exists for each eligible manager. Draft
    # start is emitted only when the draft state machine enters on_clock.
    assert len(before) == 2
    next_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=5)

    response = client.patch(
        f"/leagues/{league['id']}/draft",
        json={
            "draft_datetime_utc": next_time.isoformat(),
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 120,
        },
        headers=auth_headers(commissioner_token),
    )

    assert response.status_code == 200
    assert response.json()["draft_datetime_utc"].startswith(next_time.isoformat()[:19])
    db_session.expire_all()
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    assert draft.draft_datetime_utc.replace(tzinfo=timezone.utc) == next_time
    assert draft.draft_version == 1
    active = (
        db_session.query(ScheduledNotification)
        .filter(ScheduledNotification.league_id == league["id"], ScheduledNotification.canceled_at.is_(None))
        .all()
    )
    assert len(active) == 4
    member_user_ids = {
        row.user_id
        for row in db_session.query(LeagueMember).filter(LeagueMember.league_id == league["id"]).all()
    }
    assert {row.user_id for row in active} == member_user_ids
    reminders = [row for row in active if row.event_type == "DRAFT_1H"]
    reschedules = [row for row in active if row.event_type == "DRAFT_RESCHEDULED"]
    assert len(reminders) == 2
    assert len(reschedules) == 2
    assert all(row.scheduled_for.replace(tzinfo=timezone.utc) == next_time - timedelta(hours=1) for row in reminders)
    assert all(row.payload["draft_version"] == 1 for row in reschedules)
    canceled = (
        db_session.query(ScheduledNotification)
        .filter(ScheduledNotification.league_id == league["id"], ScheduledNotification.canceled_at.is_not(None))
        .count()
    )
    assert canceled == 2
    # Producers enqueue durable outbox rows only; the notification worker is
    # solely responsible for materializing in-app log entries after commit.
    assert not db_session.query(ScheduledNotification).filter(
        ScheduledNotification.league_id == league["id"],
        ScheduledNotification.event_type == "DRAFT_RESCHEDULED",
        ScheduledNotification.sent_at.is_not(None),
    ).count()


def test_reschedule_requires_timestamp_with_timezone_offset(client):
    token = create_user_and_token(client, "reschedule-naive")
    league = create_league(client, token, "Timezone Required")

    response = client.patch(
        f"/leagues/{league['id']}/draft",
        json={
            "draft_datetime_utc": "2026-08-20T18:00:00",
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 422
    assert "timezone offset" in response.text


def test_rescheduled_draft_does_not_start_at_the_replaced_time(client, db_session):
    token = create_user_and_token(client, "reschedule-replaced-time")
    league = create_league(client, token, "Replaced Schedule")
    old_time = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=10)
    new_time = old_time + timedelta(days=1)
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    draft.draft_datetime_utc = old_time
    db_session.commit()

    response = client.patch(
        f"/leagues/{league['id']}/draft",
        json={
            "draft_datetime_utc": new_time.isoformat(),
            "timezone": "America/New_York",
            "draft_type": "snake",
            "pick_timer_seconds": 90,
        },
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    # The lifecycle worker never starts a scheduled draft. It only progresses an
    # already-started draft, so the replaced time cannot resurrect an old schedule.
    assert process_expired_draft_picks_once(db_session, now=old_time + timedelta(seconds=1)) == {
        "auto_picked": 0,
        "skipped": 0,
    }
    db_session.expire_all()
    draft = db_session.query(Draft).filter(Draft.league_id == league["id"]).one()
    assert draft.status == "scheduled"
    assert draft.draft_datetime_utc.replace(tzinfo=timezone.utc) == new_time
