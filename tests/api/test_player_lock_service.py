from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.schemas.player import PlayerRead
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


def test_game_context_and_player_responses_use_notre_dame_title_case(db_session):
    wisconsin_player = Player(name="Wisconsin QB", position="QB", school="Wisconsin")
    notre_dame_player = Player(name="Notre Dame QB", position="QB", school="NOTRE DAME")
    db_session.add_all([wisconsin_player, notre_dame_player])
    db_session.flush()
    db_session.add(
        Game(
            season=2026,
            week=1,
            home_team="NOTRE DAME",
            away_team="Wisconsin",
            start_date=datetime(2026, 9, 6, 19, 30, tzinfo=timezone.utc),
            schedule_status="scheduled",
        )
    )
    db_session.commit()

    _starts, opponents, _locations = game_context_for_players(
        db_session,
        player_ids={wisconsin_player.id},
        season=2026,
        week=1,
    )

    assert opponents[wisconsin_player.id] == "Notre Dame"
    assert PlayerRead.model_validate(notre_dame_player).model_dump(mode="json")["school"] == "Notre Dame"
