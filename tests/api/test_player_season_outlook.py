from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_role_snapshot import PlayerRoleSnapshot
from collegefootballfantasy_api.app.models.player_season_outlook import PlayerSeasonOutlook
from collegefootballfantasy_api.app.services.player_season_outlook import (
    INSUFFICIENT_DATA,
    READY,
    build_player_season_outlook_facts,
    generate_player_season_outlook,
    get_persisted_player_season_outlook,
    persist_player_season_outlook,
    validate_player_season_outlook,
)


def _base_facts(position: str = "RB") -> dict:
    return {
        "player": {"id": 7, "name": "Taylor Example", "position": position, "school": "Example State", "class": "Junior", "position_rank": 4},
        "projection": {"season_year": 2026, "projected_points": 210.0, "position_projection_percentile": 0.9, "stats": {}, "source_sheet_id": "projection-sheet", "synced_at": None},
        "role": {"depth_order": 1, "role_status": "starter", "source": "depth-sheet", "confidence": 0.9},
        "team_context": {"current_team": "Example State", "historical_team": None, "is_transfer": False, "environment_week": 1, "expected_points_percentile": 0.8},
        "derived": {"experience_status": "Junior", "projected_role": "projected starter", "production_profile": "established fantasy production", "position_projection_label": "top-tier position projection", "team_environment_label": "one of the stronger projected team environments"},
        "historical": {"season": 2025, "team": "Example State", "games_played": 12, "rushing_yards": 1100.0, "rushing_touchdowns": 11.0, "fantasy_points": 230.0},
    }


@pytest.mark.parametrize("position", ["QB", "RB", "WR", "TE", "K"])
def test_outlook_is_position_aware_and_stays_within_copy_constraints(position: str):
    facts = _base_facts(position)
    if position == "QB":
        facts["historical"] = {"season": 2025, "team": "Example State", "passing_yards": 3200.0, "passing_touchdowns": 25.0, "fantasy_points": 250.0}
    elif position in {"WR", "TE"}:
        facts["historical"] = {"season": 2025, "team": "Example State", "receptions": 72.0, "receiving_yards": 950.0, "receiving_touchdowns": 8.0, "fantasy_points": 210.0}
    elif position == "K":
        facts["historical"] = {"season": 2025, "team": "Example State", "field_goals_made": 18.0, "extra_points_made": 36.0, "fantasy_points": 120.0}
    generated = generate_player_season_outlook(facts)
    assert generated.status == READY
    assert generated.text is not None
    assert validate_player_season_outlook(facts, generated.text) == []


@pytest.mark.parametrize("name", ["Mark Fletcher Jr.", "A.J. Turner", "T.J. Moore"])
def test_outlook_sentence_validation_ignores_name_abbreviations(name: str):
    facts = _base_facts("RB")
    text = (
        f"{name} enters 2026 at Miami as a senior RB with a projected starting role. "
        "In 2025, he recorded 500 rushing yards and 5 rushing touchdowns. "
        "The local preseason model combines verified production and role context for a grounded outlook."
    )

    errors = validate_player_season_outlook(facts, text)
    assert "outlook must contain two or three sentences" not in errors


def test_missing_projection_is_hidden_not_fabricated():
    facts = _base_facts()
    facts["projection"]["projected_points"] = None
    generated = generate_player_season_outlook(facts)
    assert generated.status == INSUFFICIENT_DATA
    assert generated.text is None


def test_outlook_uses_final_local_history_and_persisted_rows_only(db_session):
    player = Player(
        name="Local Runner", position="RB", school="Example State", player_class="Junior",
        depth_order=2, sheet_projected_season_points=176.0, sheet_source_sheet_id="projection-sheet",
    )
    db_session.add(player)
    db_session.flush()
    db_session.add_all([
        PlayerHistoricalSeasonStat(
            player_id=player.id, provider="local_import", provider_player_id="runner-7",
            season=2025, season_type="regular", team_name="Old State", rushing_yards=900,
            rushing_touchdowns=8, parser_version="TEST", imported_at=datetime.now(timezone.utc), is_final=True,
        ),
        PlayerRoleSnapshot(
            player_id=player.id, season=2026, week=1, source="verified_depth_chart",
            school="Example State", position="RB", depth_order=1, role_status="starter",
        ),
    ])
    db_session.commit()
    facts = build_player_season_outlook_facts(db_session, player, season_year=2026)
    generated = generate_player_season_outlook(facts)
    assert facts["historical"]["season"] == 2025
    assert facts["derived"]["projected_role"] == "projected starter"
    assert generated.status == READY
    row = persist_player_season_outlook(db_session, player_id=player.id, season_year=2026, generated=generated)
    db_session.commit()
    assert get_persisted_player_season_outlook(db_session, player_id=player.id, season_year=2026).id == row.id
    assert db_session.query(PlayerSeasonOutlook).count() == 1


def test_player_card_exposes_only_a_persisted_ready_outlook(client, db_session):
    """The card contract reads the reviewed batch result; it never generates copy."""
    player = Player(
        name="Contract Runner",
        position="RB",
        school="Example State",
        player_class="Junior",
        sheet_projected_season_points=176.0,
        sheet_source_sheet_id="projection-sheet",
    )
    db_session.add(player)
    db_session.flush()
    generated = generate_player_season_outlook(_base_facts("RB"))
    persist_player_season_outlook(
        db_session,
        player_id=player.id,
        season_year=2026,
        generated=generated,
    )
    db_session.commit()

    response = client.get(f"/players/{player.id}/card")

    assert response.status_code == 200
    payload = response.json()["season_outlook"]
    assert payload["season_year"] == 2026
    assert payload["outlook_type"] == "PRESEASON"
    assert payload["outlook_text"] == generated.text
