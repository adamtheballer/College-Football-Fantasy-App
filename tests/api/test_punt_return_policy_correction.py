from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.services.punt_return_policy_correction import (
    apply_punt_return_policy_correction,
    strip_retired_punt_return_rules,
)
from tests.api.scoring_helpers import create_scoring_fixture


def test_correction_removes_legacy_return_stats_and_recalculates_scores(db_session):
    league, _home, _away, players, _matchup = create_scoring_fixture(db_session)
    player = players["rb"]
    player_stat = db_session.query(PlayerStat).filter_by(
        player_id=player.id,
        season=2026,
        week=1,
    ).one()
    player_stat.stats = {
        "PuntReturnYards": 50,
        "PuntReturnTouchdowns": 1,
        "fantasy_points": 11,
    }
    game = Game(
        external_id="punt-return-fixture",
        season=2026,
        week=1,
        home_team="Test",
        away_team="Other Test",
    )
    db_session.add(game)
    db_session.flush()
    game_stat = PlayerGameStat(
        player_id=player.id,
        game_id=game.id,
        season=2026,
        week=1,
        source="espn_final_boxscore",
        stats={"punt_return_yards": 50, "punt_return_tds": 1, "fpts": 11},
    )
    db_session.add(game_stat)
    score = PlayerWeekScore(
        league_id=league.id,
        player_id=player.id,
        season=2026,
        week=1,
        fantasy_points=11,
        breakdown_json={"punt_return_tds": {"points": 6}},
    )
    db_session.add(score)
    settings = db_session.query(LeagueSettings).filter_by(league_id=league.id).one()
    settings.scoring_json = {"punt_return_tds": 6, "ppr": 1}
    historical = PlayerHistoricalSeasonStat(
        player_id=player.id,
        provider="espn",
        provider_player_id="fixture-rb",
        season=2025,
        season_type="regular",
        position="RB",
        games_played=1,
        punt_return_attempts=1,
        punt_return_yards=50,
        punt_return_touchdowns=1,
        fantasy_points=11,
        fantasy_points_per_game=11,
        parser_version="test",
        imported_at=datetime.now(timezone.utc),
    )
    db_session.add(historical)
    db_session.commit()

    summary = apply_punt_return_policy_correction(db_session)
    db_session.commit()

    db_session.refresh(player_stat)
    db_session.refresh(game_stat)
    db_session.refresh(score)
    db_session.refresh(settings)
    db_session.refresh(historical)
    assert summary.player_stats_sanitized >= 1
    assert summary.game_stats_sanitized >= 1
    assert summary.league_weeks_recalculated >= 1
    assert player_stat.stats == {}
    assert game_stat.stats == {}
    assert score.fantasy_points == 0.0
    assert "punt_return_tds" not in score.breakdown_json
    assert settings.scoring_json == {"ppr": 1}
    assert historical.punt_return_attempts is None
    assert historical.punt_return_yards is None
    assert historical.punt_return_touchdowns is None
    assert historical.fantasy_points == 0.0


def test_rule_sanitizer_handles_nested_and_legacy_alias_forms():
    assert strip_retired_punt_return_rules({
        "offense": {"PuntReturnYards": 0.1, "receptions": 1},
        "punt_return_tds": 6,
        "kicker": {"xp_made": 1},
    }) == {
        "offense": {"receptions": 1},
        "kicker": {"xp_made": 1},
    }
