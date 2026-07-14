from __future__ import annotations

import json
from pathlib import Path

from collegefootballfantasy_api.app.services.providers.espn_historical.parser import (
    ESPNHistoricalStatsParseError,
    parse_number,
    parse_player_history,
)


FIXTURE_DIR = Path("vendor/espn-college-football-stats/tests/fixtures")


def _fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def test_parse_espn_historical_passing_fixture_maps_core_stats() -> None:
    history = parse_player_history(_fixture("justin-herbert.json"), provider_player_id="4038941")

    season_2016 = next(row for row in history.seasons if row.season == 2016)

    assert season_2016.categories["passing"]["passing_completions"] == 162
    assert season_2016.categories["passing"]["passing_attempts"] == 255
    assert season_2016.categories["passing"]["passing_yards"] == 1936
    assert season_2016.categories["passing"]["passing_touchdowns"] == 19
    assert season_2016.categories["passing"]["interceptions"] == 4
    assert season_2016.categories["rushing"]["rushing_yards"] == 161
    assert season_2016.categories["rushing"]["rushing_touchdowns"] == 2


def test_parse_espn_historical_receiving_fixture_maps_core_stats() -> None:
    history = parse_player_history(_fixture("jerry-jeudy.json"), provider_player_id="4241463")

    season_2018 = next(row for row in history.seasons if row.season == 2018)

    assert season_2018.categories["receiving"]["receptions"] == 68
    assert season_2018.categories["receiving"]["receiving_yards"] == 1315
    assert season_2018.categories["receiving"]["receiving_touchdowns"] == 14


def test_parse_number_preserves_missing_and_rejects_malformed_values() -> None:
    assert parse_number("-") == (None, None)
    assert parse_number("1,305") == (1305.0, None)

    parsed, warning = parse_number("bad-value")

    assert parsed is None
    assert warning and "could not parse" in warning


def test_parse_player_history_requires_categories() -> None:
    try:
        parse_player_history({"athlete": {}}, provider_player_id="1")
    except ESPNHistoricalStatsParseError as exc:
        assert "missing categories" in str(exc)
    else:
        raise AssertionError("expected ESPNHistoricalStatsParseError")
