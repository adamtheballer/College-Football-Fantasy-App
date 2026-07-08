from datetime import datetime, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.scoring_service import finalize_league_week_scores
from collegefootballfantasy_api.app.services.standings_recalc import recalculate_standings_for_week
from tests.api.scoring_helpers import create_scoring_fixture


def test_standings_update_from_final_matchups(client, db_session):
    league, home, away, _players, _matchup = create_scoring_fixture(db_session)

    summary = finalize_league_week_scores(db_session, league.id, 2026, 1)
    db_session.commit()

    assert summary.standings_updated == 2
    home_standing = db_session.query(Standing).filter_by(league_id=league.id, team_id=home.id, season=2026, week=1).one()
    away_standing = db_session.query(Standing).filter_by(league_id=league.id, team_id=away.id, season=2026, week=1).one()
    assert (home_standing.wins, home_standing.losses, home_standing.ties) == (1, 0, 0)
    assert (away_standing.wins, away_standing.losses, away_standing.ties) == (0, 1, 0)
    assert home_standing.points_for == 56.0
    assert away_standing.points_against == 56.0


def test_standings_handle_ties_explicitly(client, db_session):
    league, home, away, _players, matchup = create_scoring_fixture(db_session)
    matchup.status = "final"
    matchup.home_score = 21.5
    matchup.away_score = 21.5

    updated = recalculate_standings_for_week(db_session, league.id, 2026, 1)
    db_session.commit()

    assert updated == 2
    home_standing = db_session.query(Standing).filter_by(league_id=league.id, team_id=home.id, season=2026, week=1).one()
    away_standing = db_session.query(Standing).filter_by(league_id=league.id, team_id=away.id, season=2026, week=1).one()
    assert (home_standing.wins, home_standing.losses, home_standing.ties) == (0, 0, 1)
    assert (away_standing.wins, away_standing.losses, away_standing.ties) == (0, 0, 1)
    assert home_standing.points_for == 21.5
    assert away_standing.points_against == 21.5


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def signup_verified_user(client, suffix: str) -> tuple[int, str]:
    email = f"scoring-{suffix}@example.com"
    response = client.post(
        "/auth/signup",
        json={"first_name": f"Scoring{suffix}", "email": email, "password": "StrongPass123!"},
    )
    assert response.status_code == 201
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == email).one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
        user_id = user.id
    return user_id, response.json()["access_token"]


def test_recalculate_endpoint_requires_commissioner(client, db_session):
    commissioner_id, commissioner_token = signup_verified_user(client, "commissioner")
    manager_id, manager_token = signup_verified_user(client, "manager")
    league, _home, _away, _players, _matchup = create_scoring_fixture(db_session)
    league.commissioner_user_id = commissioner_id
    db_session.add_all(
        [
            LeagueMember(league_id=league.id, user_id=commissioner_id, role="commissioner"),
            LeagueMember(league_id=league.id, user_id=manager_id, role="manager"),
        ]
    )
    db_session.commit()

    manager_response = client.post(
        f"/leagues/{league.id}/weeks/1/recalculate-scores",
        headers=auth_headers(manager_token),
    )
    assert manager_response.status_code == 403

    commissioner_response = client.post(
        f"/leagues/{league.id}/weeks/1/recalculate-scores",
        headers=auth_headers(commissioner_token),
    )
    assert commissioner_response.status_code == 200
    assert commissioner_response.json() == {
        "league_id": league.id,
        "season": 2026,
        "week": 1,
        "players_scored": 7,
        "teams_scored": 2,
        "matchups_updated": 1,
        "standings_updated": 2,
    }
