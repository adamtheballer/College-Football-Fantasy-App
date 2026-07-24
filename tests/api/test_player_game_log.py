from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services import player_game_log


def test_player_game_log_returns_canonical_schedule_with_bye_and_verified_stats(client, db_session):
    player = Player(name="Schedule Quarterback", position="QB", school="Ohio State")
    db_session.add(player)
    db_session.flush()
    game = Game(
        external_id="schedule-2026-w1-ohio-state-vs-texas",
        season=2026,
        week=1,
        home_team="Ohio State",
        away_team="Texas",
        home_points=31,
        away_points=24,
        neutral_site=False,
    )
    db_session.add(game)
    db_session.flush()
    db_session.add_all(
        [
            TeamSchedule(
                team_name="Ohio State",
                season=2026,
                week=0,
                location="bye",
                is_bye=True,
                neutral_site=False,
                conference_game=False,
                date_confirmed=False,
            ),
            TeamSchedule(
                team_name="Ohio State",
                season=2026,
                week=1,
                game_id=game.id,
                opponent_name="Texas",
                location="home",
                is_bye=False,
                neutral_site=False,
                conference_game=False,
                date_confirmed=True,
            ),
        ]
    )
    db_session.add(
        PlayerGameStat(
            player_id=player.id,
            game_id=game.id,
            season=2026,
            week=1,
            source="verified_boxscore",
            stats={"fantasy_points": 23.4, "passing_yards": 288, "passing_touchdowns": 3},
        )
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/game-log", params={"season": 2026})

    assert response.status_code == 200
    body = response.json()
    assert body["team_name"] == "Ohio State"
    assert [row["week"] for row in body["games"]] == [0, 1]
    assert body["games"][0]["location"] == "bye"
    assert body["games"][0]["stats"] is None
    assert body["games"][0]["stat_status"] == "not_available"
    assert body["games"][1]["opponent_name"] == "Texas"
    assert body["games"][1]["result"] == "W 31–24"
    assert body["games"][1]["game_status"] == "final"
    assert body["games"][1]["stat_status"] == "final"
    assert body["games"][1]["stats"]["fantasy_points"] == 23.4
    assert body["games"][1]["stats"]["stats"]["passing_yards"] == 288


def test_player_game_log_uses_explicit_school_alias_without_guessing(client, db_session):
    player = Player(name="Alias Receiver", position="WR", school="Cal")
    db_session.add(player)
    db_session.add(
        TeamSchedule(
            team_name="California",
            season=2026,
            week=1,
            opponent_name="UCLA",
            location="away",
            is_bye=False,
            neutral_site=False,
            conference_game=True,
            date_confirmed=True,
        )
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/game-log", params={"season": 2026})

    assert response.status_code == 200
    assert response.json()["games"][0]["opponent_name"] == "UCLA"


def test_player_game_log_attaches_weekly_live_stats_when_game_level_stats_are_unavailable(client, db_session):
    player = Player(name="Weekly Stat Receiver", position="WR", school="Ohio State")
    db_session.add(player)
    db_session.flush()
    db_session.add_all(
        [
            TeamSchedule(
                team_name="Ohio State",
                season=2026,
                week=1,
                opponent_name="Texas",
                location="home",
                is_bye=False,
                neutral_site=False,
                conference_game=False,
                date_confirmed=True,
            ),
            PlayerStat(
                player_id=player.id,
                season=2026,
                week=1,
                source="espn",
                stats={"fantasy_points": 18.2, "receiving_yards": 104},
            ),
        ]
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/game-log", params={"season": 2026})

    assert response.status_code == 200
    row = response.json()["games"][0]
    assert row["stats"]["source"] == "espn"
    assert row["game_status"] == "active"
    assert row["stat_status"] == "active"
    assert row["stats"]["fantasy_points"] == 18.2
    assert row["stats"]["stats"]["receiving_yards"] == 104


def test_player_game_log_does_not_invent_schedule_for_unmatched_school(client, db_session):
    player = Player(name="Unmatched Player", position="RB", school="Independent Program")
    db_session.add(player)
    db_session.add(
        TeamSchedule(
            team_name="Ohio State",
            season=2026,
            week=1,
            opponent_name="Texas",
            location="home",
            is_bye=False,
            neutral_site=False,
            conference_game=False,
            date_confirmed=True,
        )
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/game-log", params={"season": 2026})

    assert response.status_code == 200
    assert response.json()["games"] == []
    assert "has not been imported" in response.json()["message"]


def test_player_game_log_handles_schedule_table_not_yet_migrated(client, db_session, monkeypatch):
    player = Player(name="Pending Schedule Player", position="RB", school="Ohio State")
    db_session.add(player)
    db_session.commit()
    monkeypatch.setattr(player_game_log, "_team_schedule_table_exists", lambda db: False)

    response = client.get(f"/players/{player.id}/game-log", params={"season": 2026})

    assert response.status_code == 200
    assert response.json()["games"] == []
    assert response.json()["message"] == "The 2026 team schedule is not available yet."
