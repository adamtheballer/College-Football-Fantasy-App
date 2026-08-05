from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.services.player_trade_value import (
    MAX_TRADE_VALUE,
    VALUE_POLICY_VERSION,
    calculate_player_trade_value,
    calculate_weekly_trade_values,
    current_trade_value_snapshot,
    get_player_trade_values,
    value_tier,
    weekly_value_weights,
)
from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.team import Team
from datetime import datetime, timezone


def test_preseason_value_is_raw_rating_only_until_authoritative_week_one_finalization(db_session):
    elite = Player(name="Elite RB", position="RB", school="Texas", raw_cfb27_rating=95, cfb27_overall=95, sheet_projected_season_points=260)
    mid = Player(name="Mid RB", position="RB", school="Miami", raw_cfb27_rating=80, cfb27_overall=80, sheet_projected_season_points=180)
    db_session.add_all([elite, mid]); db_session.commit()
    preseason = calculate_player_trade_value(db_session, player_id=elite.id, season=2026, week=0)
    assert preseason.value == 95
    assert preseason.factor_breakdown_json["preseasonRating"] == 95
    assert preseason.factor_breakdown_json["seasonPerformance"] == 0
    assert preseason.factor_breakdown_json["futureProjection"] == 0
    db_session.add_all([
        PlayerStat(player_id=elite.id, season=2026, week=1, verified=True, stats={"fantasy_points": 10}),
        PlayerStat(player_id=mid.id, season=2026, week=1, verified=True, stats={"fantasy_points": 35}),
    ]); db_session.commit()
    # Week 1 data is insufficient: without finalized application matchups the
    # exact preseason value remains authoritative.
    week_one = calculate_player_trade_value(db_session, player_id=mid.id, season=2026, week=1)
    assert week_one.value == 80
    assert week_one.policy_version == "cfb27_exact_preseason_v1"

    league = League(name="Authoritative Week One", season_year=2026)
    home = Team(league=league, name="Home", owner_name="Home Owner")
    away = Team(league=league, name="Away", owner_name="Away Owner")
    db_session.add_all([league, home, away]); db_session.flush()
    db_session.add(Matchup(league_id=league.id, season=2026, week=1, home_team_id=home.id, away_team_id=away.id, status="final"))
    db_session.commit()
    week_one = calculate_player_trade_value(db_session, player_id=mid.id, season=2026, week=1)
    assert week_one.factor_breakdown_json["seasonPerformance"] > 0
    assert week_one.value > 0
    assert VALUE_POLICY_VERSION == "universal_v2"
    db_session.refresh(mid)
    assert mid.raw_cfb27_rating == 80
    assert mid.current_value_rating == week_one.value


def test_value_weights_bounds_ranks_and_repeat_generation(db_session):
    first = Player(name="First WR", position="WR", school="Ohio State", raw_cfb27_rating=99, cfb27_overall=99, sheet_projected_season_points=300)
    second = Player(name="Second WR", position="WR", school="Oregon", raw_cfb27_rating=60, cfb27_overall=60, sheet_projected_season_points=100)
    db_session.add_all([first, second]); db_session.commit()
    assert all(abs(sum(weekly_value_weights(week)) - 1) < 0.00001 for week in range(0, 16))
    first_run = calculate_weekly_trade_values(db_session, season=2026, week=0); db_session.commit()
    second_run = calculate_weekly_trade_values(db_session, season=2026, week=0); db_session.commit()
    assert first_run["calculated"] == second_run["calculated"] == 2
    value_rows = db_session.query(__import__("collegefootballfantasy_api.app.models.player_trade_value", fromlist=["PlayerTradeValue"]).PlayerTradeValue).all()
    assert len(value_rows) == 2
    assert all(0 <= row.value <= MAX_TRADE_VALUE for row in value_rows)
    assert min(row.positional_value_rank for row in value_rows) == 1


def test_trade_value_tiers_and_serialized_legacy_values_use_the_0_to_99_scale(db_session):
    player = Player(name="Tier Receiver", position="WR", school="Miami", raw_cfb27_rating=88, current_value_rating=88, value_policy_version="cfb27_exact_preseason_v1", cfb27_overall=88)
    db_session.add(player)
    db_session.flush()
    db_session.add(
        PlayerTradeValue(
            player_id=player.id,
            season=2026,
            week=0,
            value=100.0,
            tier="ELITE",
            confidence=0.9,
            policy_version="cfb27_exact_preseason_v1",
            calculated_at=datetime.now(timezone.utc),
            input_version="legacy",
        )
    )
    db_session.commit()

    assert [value_tier(value) for value in (96, 90, 85, 80, 78, 70, 69)] == [
        "UNTOUCHABLE",
        "FRANCHISE_STAR",
        "EFFECTIVE_STARTER",
        "GREAT_OPTION",
        "GOOD_BENCH_OPTION",
        "GREAT_DEPTH_ROLE",
        "SPECULATIVE",
    ]
    history = get_player_trade_values(db_session, player_id=player.id, season=2026)
    assert history.current is not None
    assert history.current.value == 88.0
    assert history.current.tier == "EFFECTIVE_STARTER"


def test_preseason_contract_ignores_stale_dynamic_value_and_keeps_jeremiah_at_99(db_session):
    jeremiah = Player(
        name="Jeremiah Smith",
        position="WR",
        school="Ohio State",
        cfb27_overall=99,
        raw_cfb27_rating=99,
        current_value_rating=91,
        value_policy_version="universal_v1",
    )
    db_session.add(jeremiah)
    db_session.flush()
    db_session.add(PlayerTradeValue(
        player_id=jeremiah.id, season=2026, week=1, value=91, tier="FRANCHISE_STAR",
        confidence=1, policy_version="universal_v1", calculated_at=datetime.now(timezone.utc), input_version="legacy",
    ))
    db_session.commit()

    values = get_player_trade_values(db_session, player_id=jeremiah.id, season=2026)
    snapshot = current_trade_value_snapshot(db_session, player_id=jeremiah.id, season=2026)

    assert values.current is not None
    assert values.current.raw_cfb27_rating == 99
    assert values.current.current_value_rating == 99
    assert values.current.value == 99
    assert values.current.policy_version == "cfb27_exact_preseason_v1"
    assert snapshot is not None and snapshot["value"] == 99


def test_preseason_current_value_is_exposed_consistently_by_player_card_and_trade_api(client, db_session):
    arch = Player(
        name="Arch Manning",
        position="QB",
        school="Texas",
        cfb27_overall=91,
        raw_cfb27_rating=91,
    )
    jeremiah = Player(
        name="Jeremiah Smith",
        position="WR",
        school="Ohio State",
        cfb27_overall=99,
        raw_cfb27_rating=99,
    )
    db_session.add_all([arch, jeremiah])
    db_session.commit()

    # Initialization is idempotent and makes the database field match the
    # immutable CFB27 rating before any Week 1 result is finalized.
    calculate_player_trade_value(db_session, player_id=arch.id, season=2026, week=0)
    calculate_player_trade_value(db_session, player_id=jeremiah.id, season=2026, week=0)
    db_session.commit()

    for player, expected in ((arch, 91), (jeremiah, 99)):
        player_response = client.get(f"/players/{player.id}")
        card_response = client.get(f"/players/{player.id}/card")
        value_response = client.get(f"/players/{player.id}/trade-values", params={"season": 2026})

        assert player_response.status_code == card_response.status_code == value_response.status_code == 200
        assert player_response.json()["raw_cfb27_rating"] == expected
        assert player_response.json()["current_value_rating"] == expected
        assert card_response.json()["player"]["current_value_rating"] == expected
        assert value_response.json()["current"]["current_value_rating"] == expected


def test_value_endpoint_has_no_projection_or_legacy_rating_fallback(db_session):
    player = Player(
        name="Missing Rating", position="TE", school="Miami", cfb27_overall=95,
        current_value_rating=91, sheet_projected_season_points=999,
    )
    db_session.add(player); db_session.commit()
    assert get_player_trade_values(db_session, player_id=player.id, season=2026).current is None
    assert current_trade_value_snapshot(db_session, player_id=player.id, season=2026) is None
