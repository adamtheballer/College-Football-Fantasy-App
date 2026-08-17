from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.player_lock_service import game_context_for_players


def test_game_context_includes_kickoff_opponent_and_home_away_location(db_session):
    home_player = Player(name="Home QB", position="QB", school="Texas")
    away_player = Player(name="Away QB", position="QB", school="Ohio State")
    db_session.add_all([home_player, away_player])
    db_session.flush()
    kickoff = datetime(2026, 8, 29, 16, 0, tzinfo=timezone.utc)
    db_session.add(
        Game(
            season=2026,
            week=1,
            home_team="Texas",
            away_team="Ohio State",
            start_date=kickoff,
            schedule_status="scheduled",
        )
    )
    db_session.commit()

    starts, opponents, locations = game_context_for_players(
        db_session,
        player_ids={home_player.id, away_player.id},
        season=2026,
        week=1,
    )

    assert starts == {home_player.id: kickoff, away_player.id: kickoff}
    assert opponents == {home_player.id: "Ohio State", away_player.id: "Texas"}
    assert locations == {home_player.id: "home", away_player.id: "away"}


def test_game_context_returns_the_full_contract_for_an_empty_roster(db_session):
    starts, opponents, locations = game_context_for_players(
        db_session,
        player_ids=set(),
        season=2026,
        week=1,
    )

    assert starts == {}
    assert opponents == {}
    assert locations == {}
