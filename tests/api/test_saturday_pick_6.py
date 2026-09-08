from datetime import datetime, timedelta, timezone

from conftest import admin_headers

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.saturday_pick import SaturdayPickContest, SaturdayPickPlayer
from collegefootballfantasy_api.app.models.saturday_pick import SaturdayPickContentAudit
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.saturday_pick import SaturdayPickContestCreate
from collegefootballfantasy_api.app.services.saturday_pick_service import validate_contest_readiness


def _enable_pick_6(monkeypatch, *, sponsors=False):
    monkeypatch.setattr(settings, "saturday_pick_6_enabled", True)
    monkeypatch.setattr(settings, "saturday_pick_6_public_enabled", True)
    monkeypatch.setattr(settings, "saturday_pick_6_sponsors_enabled", sponsors)


def _featured_players(db_session, *, position="QB", final_games=False, with_weekly_projections=True):
    kickoff = datetime.now(timezone.utc) + timedelta(hours=4)
    players = []
    for index in range(6):
        player = Player(name=f"{position} Featured {index}", position=position, school=f"School {index}")
        db_session.add(player)
        db_session.flush()
        game = Game(
            season=2026,
            week=1,
            home_team=f"Opponent {index}",
            away_team=player.school,
            start_date=kickoff + timedelta(minutes=index),
            home_points=10 if final_games else None,
            away_points=20 if final_games else None,
            schedule_status="final" if final_games else "scheduled",
        )
        db_session.add(game)
        db_session.flush()
        db_session.add(TeamSchedule(
            team_name=player.school,
            season=2026,
            week=1,
            game_id=game.id,
            opponent_name=game.home_team,
            location="away",
            is_bye=False,
            kickoff_at=game.start_date,
        ))
        if with_weekly_projections:
            db_session.add(WeeklyProjection(
                player_id=player.id,
                season=2026,
                week=1,
                is_published=True,
                projection_version="FINAL",
                fantasy_points=18.0 + index,
            ))
        if final_games:
            db_session.add(PlayerGameStat(
                player_id=player.id,
                game_id=game.id,
                season=2026,
                week=1,
                source="test",
                stats={"pass_yards": 200 + index * 25, "pass_tds": 1},
            ))
        players.append(player)
    db_session.commit()
    return players, kickoff


def _create_payload(players, lock_at, *, position="QB", **extra):
    return {
        "season": 2026,
        "week_number": 1,
        "contest_position": position,
        "featured_player_ids": [player.id for player in players],
        "lock_at": lock_at.isoformat(),
        **extra,
    }


def test_contest_readiness_is_select_only_and_does_not_allocate_contest_rows(db_session):
    players, kickoff = _featured_players(db_session, position="RB")
    payload = SaturdayPickContestCreate(**_create_payload(players, kickoff, position="RB"))
    contest_count_before = db_session.query(SaturdayPickContest).count()
    featured_count_before = db_session.query(SaturdayPickPlayer).count()

    readiness = validate_contest_readiness(db_session, payload)

    assert readiness.lock_at == kickoff
    assert [player.name for player, _ in readiness.featured] == [player.name for player in players]
    assert not db_session.new
    assert not db_session.dirty
    assert db_session.query(SaturdayPickContest).count() == contest_count_before
    assert db_session.query(SaturdayPickPlayer).count() == featured_count_before


def test_admin_review_preparation_creates_an_auditable_unpublished_contest(client, db_session):
    _players, _kickoff = _featured_players(db_session, position="RB")
    headers = admin_headers(client)

    prepared = client.post(
        "/admin/saturday-pick-6/prepare",
        json={"season": 2026, "week_number": 1, "reason": "Weekly candidate review"},
        headers=headers,
    )

    assert prepared.status_code == 201
    payload = prepared.json()
    assert payload["contest"]["status"] == "SCHEDULED"
    assert len(payload["contest"]["players"]) == 6
    assert payload["audit"][0]["action"] == "prepared"
    assert db_session.query(SaturdayPickContentAudit).count() == 1


def test_admin_rejects_mixed_position_and_wrong_field_size(client, db_session):
    players, kickoff = _featured_players(db_session)
    player = players[-1]
    player.position = "RB"
    db_session.commit()

    mixed = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff), headers=admin_headers(client))
    assert mixed.status_code == 422
    assert "match the contest position" in mixed.json()["detail"]

    player.position = "QB"
    db_session.commit()
    short = client.post(
        "/admin/saturday-pick-6",
        json=_create_payload(players[:5], kickoff),
        headers=admin_headers(client),
    )
    assert short.status_code == 422
    assert "exactly six" in short.json()["detail"]


def test_contest_lock_is_the_first_featured_player_kickoff_and_identifies_that_player(client, db_session):
    players, kickoff = _featured_players(db_session)
    headers = admin_headers(client)

    early_lock = client.post(
        "/admin/saturday-pick-6",
        json=_create_payload(players, kickoff - timedelta(minutes=1)),
        headers=headers,
    )
    assert early_lock.status_code == 422
    assert "locks exactly" in early_lock.json()["detail"]

    created = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff), headers=headers)
    assert created.status_code == 201
    payload = created.json()
    assert datetime.fromisoformat(payload["lock_at"].replace("Z", "+00:00")).replace(tzinfo=timezone.utc) == kickoff
    assert payload["first_game_player"] == {
        "id": payload["players"][0]["id"],
        "player_id": players[0].id,
        "player_name": players[0].name,
        "opponent": "Opponent 0",
        "game_time": payload["lock_at"],
    }

    published = client.post(f"/admin/saturday-pick-6/{payload['id']}/publish", json={}, headers=headers)
    assert published.status_code == 200
    assert datetime.fromisoformat(published.json()["lock_at"].replace("Z", "+00:00")).replace(tzinfo=timezone.utc) == kickoff


def test_scheduled_contest_is_visible_but_cannot_open_without_six_verified_weekly_projections(client, db_session, monkeypatch):
    _enable_pick_6(monkeypatch)
    players, kickoff = _featured_players(db_session, with_weekly_projections=False)
    headers = admin_headers(client)
    created = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff), headers=headers)
    assert created.status_code == 201
    assert created.json()["status"] == "SCHEDULED"
    assert all(player["projected_points"] is None for player in created.json()["players"])

    signup = client.post("/auth/signup", json={"first_name": "Scheduled", "email": "scheduled@example.com", "password": "StrongPass123!"})
    user_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    current = client.get("/saturday-pick-6/current", params={"season": 2026, "week": 1}, headers=user_headers)
    assert current.status_code == 200
    assert current.json()["status"] == "SCHEDULED"

    published = client.post(f"/admin/saturday-pick-6/{created.json()['id']}/publish", json={}, headers=headers)
    assert published.status_code == 422
    assert "verified weekly projections" in published.json()["detail"]


def test_saturday_pick_hides_featured_player_headshots_for_public_beta(client, db_session):
    players, kickoff = _featured_players(db_session)
    for player in players:
        player.image_url = f"https://assets.espn.test/{player.id}.png"
        player.espn_headshot_url = f"https://assets.espn.test/{player.id}-profile.png"
    db_session.commit()

    response = client.post(
        "/admin/saturday-pick-6",
        json=_create_payload(players, kickoff),
        headers=admin_headers(client),
    )

    assert response.status_code == 201
    assert all(row["image_url"] is None for row in response.json()["players"])


def test_saturday_pick_hides_existing_sponsor_data_when_beta_sponsors_are_disabled(client, db_session, monkeypatch):
    _enable_pick_6(monkeypatch)
    players, kickoff = _featured_players(db_session)
    response = client.post(
        "/admin/saturday-pick-6",
        json=_create_payload(
            players,
            kickoff,
            sponsor_name="Example Sponsor",
            sponsor_logo_url="https://assets.example.test/sponsor.png",
            sponsor_code="BETA-CODE",
        ),
        headers=admin_headers(client),
    )

    assert response.status_code == 201
    assert response.json()["sponsor"] is None


def test_public_entry_can_change_before_lock_and_rejects_after_lock(client, db_session, monkeypatch):
    _enable_pick_6(monkeypatch)
    players, kickoff = _featured_players(db_session)
    headers = admin_headers(client)
    created = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff), headers=headers)
    assert created.status_code == 201
    contest_id = created.json()["id"]
    assert client.post(f"/admin/saturday-pick-6/{contest_id}/publish", json={}, headers=headers).status_code == 200

    signup = client.post("/auth/signup", json={"first_name": "Picker", "email": "picker@example.com", "password": "StrongPass123!"})
    user_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    first = client.put(f"/saturday-pick-6/{contest_id}/entry", json={"selected_pick_player_id": created.json()["players"][0]["id"]}, headers=user_headers)
    changed = client.put(f"/saturday-pick-6/{contest_id}/entry", json={"selected_pick_player_id": created.json()["players"][1]["id"]}, headers=user_headers)
    assert first.status_code == 200
    assert changed.status_code == 200
    assert changed.json()["selected_pick_player_id"] == created.json()["players"][1]["id"]

    from collegefootballfantasy_api.app.models.saturday_pick import SaturdayPickContest
    contest = db_session.get(SaturdayPickContest, contest_id)
    contest.lock_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    contest.status = "OPEN"
    db_session.commit()
    locked = client.put(f"/saturday-pick-6/{contest_id}/entry", json={"selected_pick_player_id": created.json()["players"][2]["id"]}, headers=user_headers)
    assert locked.status_code == 409


def test_finalization_marks_tied_winners_and_hides_sponsor_code_from_losers(client, db_session, monkeypatch):
    _enable_pick_6(monkeypatch, sponsors=True)
    players, kickoff = _featured_players(db_session, final_games=True)
    headers = admin_headers(client)
    created = client.post(
        "/admin/saturday-pick-6",
        json=_create_payload(players, kickoff, sponsor_name="Example Sponsor", sponsor_code="WINNER-ONLY"),
        headers=headers,
    )
    assert created.status_code == 201
    contest_id = created.json()["id"]
    assert client.post(f"/admin/saturday-pick-6/{contest_id}/publish", json={}, headers=headers).status_code == 200

    winner_signup = client.post("/auth/signup", json={"first_name": "Winner", "email": "winner@example.com", "password": "StrongPass123!"})
    winner_headers = {"Authorization": f"Bearer {winner_signup.json()['access_token']}"}
    winner_entry = client.put(
        f"/saturday-pick-6/{contest_id}/entry",
        json={"selected_pick_player_id": created.json()["players"][0]["id"]},
        headers=winner_headers,
    )
    assert winner_entry.status_code == 200

    loser_signup = client.post("/auth/signup", json={"first_name": "Loser", "email": "loser@example.com", "password": "StrongPass123!"})
    loser_headers = {"Authorization": f"Bearer {loser_signup.json()['access_token']}"}
    loser_entry = client.put(
        f"/saturday-pick-6/{contest_id}/entry",
        json={"selected_pick_player_id": created.json()["players"][2]["id"]},
        headers=loser_headers,
    )
    assert loser_entry.status_code == 200

    # Force the first two players into an exact tie under canonical scoring.
    stats = db_session.query(PlayerGameStat).order_by(PlayerGameStat.player_id.asc()).all()
    stats[0].stats = {"pass_yards": 1_000, "pass_tds": 2}
    stats[1].stats = {"pass_yards": 1_000, "pass_tds": 2}
    db_session.commit()
    finalized = client.post(f"/admin/saturday-pick-6/{contest_id}/finalize", headers=headers)
    assert finalized.status_code == 200
    winning_ids = finalized.json()["winning_player_ids"]
    assert len(winning_ids) == 2

    winner_contest = client.get(f"/saturday-pick-6/{contest_id}", headers=winner_headers).json()
    loser_contest = client.get(f"/saturday-pick-6/{contest_id}", headers=loser_headers).json()
    losing_featured = next(row for row in loser_contest["players"] if row["player_id"] not in winning_ids)
    assert winner_contest["entry"]["is_winner"] is True
    assert winner_contest["sponsor"]["reward_unlocked"] is True
    assert winner_contest["sponsor"]["code"] == "WINNER-ONLY"
    # A finalized losing entry must never receive the sponsor code.
    assert loser_contest["entry"]["is_winner"] is False
    assert loser_contest["sponsor"]["code"] is None
    assert losing_featured["final_points"] is not None
    rewards = client.get("/saturday-pick-6/rewards", headers=winner_headers)
    assert rewards.status_code == 200
    assert rewards.json()[0]["sponsor"]["code"] == "WINNER-ONLY"
    assert client.get("/saturday-pick-6/rewards", headers=loser_headers).json() == []
    assert client.get("/saturday-pick-6/rewards").status_code == 401


def test_rotation_is_rb_wr_qb_and_repeats():
    from collegefootballfantasy_api.app.services.saturday_pick_service import recommended_position
    assert [recommended_position(week) for week in range(1, 8)] == ["RB", "WR", "QB", "RB", "WR", "QB", "RB"]


def test_worker_finalizes_verified_games_once_and_repairs_exact_sheet_links(client, db_session, monkeypatch):
    from collegefootballfantasy_api.app.services.saturday_pick_service import refresh_open_pick_contests
    _enable_pick_6(monkeypatch)
    players, kickoff = _featured_players(db_session, final_games=True)
    headers = admin_headers(client)
    created = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff), headers=headers).json()
    client.post(f"/admin/saturday-pick-6/{created['id']}/publish", json={}, headers=headers)
    contest = db_session.get(SaturdayPickContest, created["id"])
    contest.lock_at = datetime.now(timezone.utc) - timedelta(hours=1)
    featured = db_session.query(SaturdayPickPlayer).filter_by(contest_id=contest.id).first()
    actual_game = db_session.get(Game, featured.game_id)
    actual_game.external_id = "12345678"
    placeholder = Game(season=2026, week=1, external_id="sheet-old-event", home_team=actual_game.home_team,
                       away_team=actual_game.away_team, start_date=actual_game.start_date)
    db_session.add(placeholder)
    db_session.flush()
    featured.game_id = placeholder.id
    db_session.commit()
    result = refresh_open_pick_contests(db_session)
    assert result["finalized"] == 1
    assert contest.status == "FINAL"
    assert featured.game_id == actual_game.id
    assert featured.scoring_status == "FINAL"
    finalized_at = contest.finalized_at
    assert refresh_open_pick_contests(db_session)["finalized"] == 0
    assert contest.finalized_at == finalized_at


def test_nonzero_team_scores_do_not_prove_final_and_missing_stats_never_award(client, db_session, monkeypatch):
    from collegefootballfantasy_api.app.services.saturday_pick_service import refresh_open_pick_contests
    _enable_pick_6(monkeypatch)
    players, kickoff = _featured_players(db_session, final_games=True)
    headers = admin_headers(client)
    created = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff), headers=headers).json()
    client.post(f"/admin/saturday-pick-6/{created['id']}/publish", json={}, headers=headers)
    contest = db_session.get(SaturdayPickContest, created["id"])
    contest.lock_at = datetime.now(timezone.utc) - timedelta(hours=1)
    featured = db_session.query(SaturdayPickPlayer).filter_by(contest_id=contest.id).first()
    game = db_session.get(Game, featured.game_id)
    game.schedule_status = "in_progress"
    featured.game_time = contest.lock_at
    db_session.commit()
    assert refresh_open_pick_contests(db_session)["finalized"] == 0
    assert featured.scoring_status == "LIVE"
    game.schedule_status = "final"
    db_session.query(PlayerGameStat).filter_by(player_id=featured.player_id).delete()
    db_session.commit()
    assert refresh_open_pick_contests(db_session)["finalized"] == 0
    assert featured.scoring_status == "DATA_DELAYED"
    assert contest.status == "PROVISIONAL"
    assert contest.winning_player_ids_json is None
    db_session.add(PlayerGameStat(player_id=featured.player_id, game_id=game.id, season=2026, week=1,
                                 source="test-verified", stats={"rush_yards": 50}))
    db_session.commit()
    assert refresh_open_pick_contests(db_session)["finalized"] == 1


def test_weekly_publication_uses_published_ranks_at_reset_and_is_idempotent(client, db_session, monkeypatch):
    from collegefootballfantasy_api.app.services import saturday_pick_service as service
    from collegefootballfantasy_api.app.services.player_season_rank import PlayerSeasonPositionalRank
    _enable_pick_6(monkeypatch)
    players, kickoff = _featured_players(db_session, position="RB")
    headers = admin_headers(client)
    template = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff, position="RB"), headers=headers).json()
    client.post(f"/admin/saturday-pick-6/{template['id']}/publish", json={}, headers=headers)
    for player in players:
        player.position = "WR"
        db_session.add(TeamSchedule(team_name=player.school, season=2026, week=2, opponent_name="Next opponent",
                                   kickoff_at=datetime(2026, 9, 12, 18, tzinfo=timezone.utc), location="home", is_bye=False))
        db_session.add(WeeklyProjection(player_id=player.id, season=2026, week=2, fantasy_points=20,
                                       projection_version="FINAL", is_published=True, projection_status="ACTIVE"))
    db_session.commit()
    ordered = list(reversed(players))
    monkeypatch.setattr(service, "season_positional_ranks", lambda *args, **kwargs: {
        p.id: PlayerSeasonPositionalRank("WR", i + 1, 100 - i, 1) for i, p in enumerate(ordered)
    })
    monkeypatch.setattr(service, "utc_now", lambda: datetime(2026, 9, 8, 11, 59, 59, tzinfo=timezone.utc))
    assert service.ensure_weekly_contest(db_session) == 0
    monkeypatch.setattr(service, "utc_now", lambda: datetime(2026, 9, 8, 12, tzinfo=timezone.utc))
    first_projection = db_session.query(WeeklyProjection).filter_by(player_id=ordered[0].id, week=2).one()
    first_projection.is_published = False
    db_session.flush()
    assert service.ensure_weekly_contest(db_session) == 0
    first_projection.is_published = True
    db_session.flush()
    assert service.ensure_weekly_contest(db_session) == 1
    contest = db_session.query(SaturdayPickContest).filter_by(week_number=2).one()
    assert contest.contest_position == "WR"
    assert contest.status == "OPEN"
    assert [row.player_id for row in db_session.query(SaturdayPickPlayer).filter_by(contest_id=contest.id).order_by(SaturdayPickPlayer.sort_order)] == [p.id for p in ordered]
    assert service.ensure_weekly_contest(db_session) == 0


def test_live_refresh_uses_canonical_stats_without_zeroing_delayed_players(client, db_session, monkeypatch):
    _enable_pick_6(monkeypatch)
    players, kickoff = _featured_players(db_session)
    headers = admin_headers(client)
    created = client.post("/admin/saturday-pick-6", json=_create_payload(players, kickoff), headers=headers)
    contest_id = created.json()["id"]
    assert client.post(f"/admin/saturday-pick-6/{contest_id}/publish", json={}, headers=headers).status_code == 200

    featured = db_session.query(SaturdayPickPlayer).filter(SaturdayPickPlayer.contest_id == contest_id).order_by(SaturdayPickPlayer.id).all()
    contest = db_session.get(SaturdayPickContest, contest_id)
    contest.lock_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    contest.status = "OPEN"
    featured[0].game_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    db_session.add(PlayerGameStat(
        player_id=featured[0].player_id,
        game_id=featured[0].game_id,
        season=2026,
        week=1,
        source="test-live",
        stats={"rush_yards": 81, "rush_tds": 1},
    ))
    db_session.commit()

    refreshed = client.post(f"/admin/saturday-pick-6/{contest_id}/refresh", headers=headers)
    assert refreshed.status_code == 200
    payload = refreshed.json()
    assert payload["status"] == "SCORING"
    assert payload["players"][0]["scoring_status"] == "LIVE"
    assert payload["players"][0]["live_points"] > 0
    assert payload["players"][1]["live_points"] is None
    assert payload["players"][1]["scoring_status"] == "NOT_STARTED"

    active = client.get("/saturday-pick-6/active", params={"season": 2026, "week": 1}, headers=headers)
    results = client.get(f"/saturday-pick-6/{contest_id}/results", headers=headers)
    assert active.status_code == 200
    assert results.status_code == 200
