from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.player_game_display import player_game_display_state
from collegefootballfantasy_api.app.services import notification_service, sportsdata_sync


def _week_zero_fixture(db_session):
    player = Player(name="Week Zero Trojan", position="RB", school="USC")
    week_zero = Game(
        external_id="week-zero-usc",
        season=2026,
        week=0,
        home_team="USC",
        away_team="San José State",
        home_points=31,
        away_points=10,
    )
    week_one = Game(
        external_id="week-one-usc",
        season=2026,
        week=1,
        home_team="USC",
        away_team="Fresno State",
    )
    db_session.add_all([player, week_zero, week_one])
    db_session.flush()
    db_session.add_all(
        [
            TeamSchedule(
                team_name="USC", season=2026, week=0, game_id=week_zero.id,
                opponent_name="San José State", location="home", is_bye=False,
                kickoff_at=datetime(2026, 8, 29, 19, tzinfo=timezone.utc),
            ),
            TeamSchedule(
                team_name="USC", season=2026, week=1, game_id=week_one.id,
                opponent_name="Fresno State", location="home", is_bye=False,
                kickoff_at=datetime(2026, 9, 5, 19, tzinfo=timezone.utc),
            ),
            PlayerGameStat(
                player_id=player.id, game_id=week_zero.id, season=2026, week=0,
                source="espn_final_boxscore", stats={"rushing_attempts": 17, "rushing_yards": 98},
            ),
            PlayerStat(
                player_id=player.id, season=2026, week=0, source="espn",
                stats={"rushing_attempts": 17, "rushing_yards": 98},
            ),
        ]
    )
    db_session.commit()
    return player


def test_week_zero_game_log_is_retained_and_card_keeps_result_until_24_hour_cutoff(client, db_session):
    player = _week_zero_fixture(db_session)

    state = player_game_display_state(
        db_session,
        player=player,
        season=2026,
        now=datetime(2026, 9, 3, 18, tzinfo=timezone.utc),
    )
    assert state.state == "completed"
    assert state.week == 0
    assert state.stats == {"rushing_attempts": 17, "rushing_yards": 98}

    response = client.get(f"/players/{player.id}/game-log", params={"season": 2026})
    assert response.status_code == 200
    week_zero = response.json()["games"][0]
    assert week_zero["week"] == 0
    assert week_zero["game_status"] == "final"
    assert week_zero["stats"]["stats"]["rushing_yards"] == 98


def test_week_zero_card_transitions_only_that_player_to_next_kickoff_inside_24_hours(db_session):
    player = _week_zero_fixture(db_session)

    state = player_game_display_state(
        db_session,
        player=player,
        season=2026,
        now=datetime(2026, 9, 4, 19, 1, tzinfo=timezone.utc),
    )

    assert state.state == "upcoming"
    assert state.week == 1
    assert state.opponent_name == "Fresno State"
    assert state.stats is None
    assert state.transition_at == datetime(2026, 9, 4, 19, tzinfo=timezone.utc)


def test_normal_week_one_only_player_has_no_week_zero_history_or_reset(db_session):
    player = Player(name="Normal Opener", position="WR", school="Normal State")
    game = Game(season=2026, week=1, home_team="Normal State", away_team="Opponent")
    db_session.add_all([player, game])
    db_session.flush()
    db_session.add(TeamSchedule(
        team_name="Normal State", season=2026, week=1, game_id=game.id,
        opponent_name="Opponent", location="home", is_bye=False,
        kickoff_at=datetime(2026, 9, 5, 19, tzinfo=timezone.utc),
    ))
    db_session.commit()

    state = player_game_display_state(
        db_session,
        player=player,
        season=2026,
        now=datetime(2026, 9, 3, 18, tzinfo=timezone.utc),
    )
    assert state.state == "upcoming"
    assert state.week == 1
    assert state.stats is None


def test_schedule_sync_ingests_week_zero_without_rebuilding_any_fantasy_week(db_session, monkeypatch):
    class FakeSportsDataClient:
        def get_schedule(self, *, season):
            assert season == 2026
            return [{
                "Week": 0,
                "GameID": "week-zero-provider-game",
                "HomeTeamName": "USC",
                "AwayTeamName": "San José State",
                "DateTime": "2026-08-29T19:00:00Z",
                "HomeScore": 31,
                "AwayScore": 10,
            }]

    calls: list[set[int]] = []
    monkeypatch.setattr(sportsdata_sync.settings, "sportsdata_enabled", True)
    monkeypatch.setattr(sportsdata_sync, "SportsDataClient", FakeSportsDataClient)
    monkeypatch.setattr(
        notification_service,
        "rebuild_matchup_start_notifications_for_schedule",
        lambda _db, *, season, weeks: calls.append(weeks),
    )

    result = sportsdata_sync.sync_power4_schedule_from_sportsdata(db_session, season=2026)
    db_session.commit()

    assert result == {"created": 1, "updated": 0, "skipped": 0}
    game = db_session.query(Game).filter_by(external_id="week-zero-provider-game").one()
    assert game.week == 0
    assert calls == [set()]
