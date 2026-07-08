from datetime import datetime, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.projection_input_audit import ProjectionInputAudit
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_environment import TeamEnvironment
from collegefootballfantasy_api.app.models.usage_share import UsageShare
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_user(client, suffix: str) -> dict:
    response = client.post(
        "/auth/signup",
        json={"first_name": f"Projection{suffix}", "email": f"projection-meta-{suffix}@example.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 201
    payload = response.json()
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == f"projection-meta-{suffix}@example.com").one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
    return {"user": payload["user"], "access_token": payload["access_token"]}


def create_league(client, token: str) -> dict:
    response = client.post(
        "/leagues",
        json={
            "basics": {
                "name": "Projection Metadata League",
                "season_year": 2026,
                "max_teams": 2,
                "is_private": True,
                "description": None,
                "icon_url": None,
            },
            "settings": {
                "scoring_json": {"ppr": 1},
                "roster_slots_json": {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "K": 1, "BENCH": 2},
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
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["league"]


def seed_projection(db_session, league_id: int):
    player = Player(name="Projection Meta WR", position="WR", school="Texas")
    db_session.add(player)
    db_session.flush()
    projection = WeeklyProjection(
        player_id=player.id,
        season=2026,
        week=1,
        targets=8,
        receptions=5,
        rec_yards=75,
        rec_tds=1,
        fantasy_points=18.5,
        floor=10,
        ceiling=28,
        boom_prob=0.22,
        bust_prob=0.11,
        projection_version=2,
        model_version="projection-v2",
        input_snapshot_hash="abc123",
        generated_at=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
        source_freshness="fresh",
        confidence_score=0.82,
    )
    db_session.add_all(
        [
            projection,
            TeamEnvironment(team_name="Texas", season=2026, week=1, expected_plays=72, expected_points=31, pass_rate=0.55, rush_rate=0.45),
            UsageShare(player_id=player.id, season=2026, week=1, rush_share=0.02, target_share=0.24),
            PlayerWeekScore(league_id=league_id, player_id=player.id, season=2026, week=1, fantasy_points=20.0, breakdown_json={}),
        ]
    )
    db_session.commit()
    return player


def test_projection_read_returns_version_confidence_and_uncertainty_labels(client, db_session):
    identity = create_user(client, "read")
    league = create_league(client, identity["access_token"])
    player = seed_projection(db_session, league["id"])

    response = client.get(
        f"/projections/{player.id}",
        params={"season": 2026, "week": 1, "league_id": league["id"]},
        headers=auth_headers(identity["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == "projection-v2"
    assert body["projection_version"] == 2
    assert body["input_snapshot_hash"] == "abc123"
    assert body["source_freshness"] == "fresh"
    assert body["confidence_score"] == 0.82
    assert body["confidence_label"] == "High confidence"
    assert body["uncertainty_labels"] == []
    assert body["league_fantasy_points"] is not None


def test_projection_explanation_is_structured_and_audited(client, db_session):
    identity = create_user(client, "explain")
    league = create_league(client, identity["access_token"])
    player = seed_projection(db_session, league["id"])

    response = client.get(f"/projections/{player.id}/explanations", params={"season": 2026, "week": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["input_snapshot_hash"] == "abc123"
    assert body["confidence_label"] == "High confidence"
    assert "baseline" in body["explanation"]
    assert "opponent_adjustment" in body["explanation"]
    assert "injury_adjustment" in body["explanation"]
    assert "usage_adjustment" in body["explanation"]
    assert "weather_game_environment" in body["explanation"]
    assert "final_projection" in body["explanation"]
    assert "confidence" in body["explanation"]

    db_session.expire_all()
    audit = db_session.query(ProjectionInputAudit).filter(ProjectionInputAudit.player_id == player.id).one()
    assert audit.input_snapshot_hash == "abc123"
    assert audit.model_version == "projection-v2"
    assert audit.source_freshness["projection"] == "fresh"


def test_projection_backtest_returns_mae_bias_and_calibration(client, db_session):
    identity = create_user(client, "backtest")
    league = create_league(client, identity["access_token"])
    player = seed_projection(db_session, league["id"])
    settings = db_session.query(LeagueSettings).filter(LeagueSettings.league_id == league["id"]).one()
    assert settings.scoring_json["ppr"] == 1

    response = client.get(
        "/projections/backtest",
        params={"season": 2026, "week": 1, "league_id": league["id"]},
        headers=auth_headers(identity["access_token"]),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sample_size"] == 1
    assert body["mae"] == 1.5
    assert body["bias"] == 1.5
    assert body["mae_by_position"] == {"WR": 1.5}
    assert body["bias_by_team"] == {"Texas": 1.5}
    assert body["confidence_calibration"]["high"]["sample_size"] == 1
    assert body["rows"][0]["player_id"] == player.id
