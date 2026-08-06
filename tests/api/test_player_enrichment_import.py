from datetime import date

from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.player_enrichment_import import (
    EnrichmentSourceRow,
    MatchOutcome,
    import_historical_totals,
    import_identities_and_bios,
    import_weekly_projections,
    resolve_identity,
)
from collegefootballfantasy_api.app.services.player_game_log import build_player_game_log


def source_row(**overrides) -> EnrichmentSourceRow:
    values = {
        "provider": "espn",
        "provider_player_id": "5084047",
        "provider_team_id": "251",
        "provider_team_name": "Texas Longhorns",
        "player_name": "Arch Manning",
        "school": "Texas",
        "position": "QB",
        "height": "6' 4\"",
        "weight": "225 lbs",
        "birthplace": "New Orleans, LA, USA",
        "jersey": "16",
        "player_class": "JR",
        "profile_status": "Active",
        "headshot_approved": "false",
        "source_url": "https://approved.example/player/5084047",
    }
    values.update(overrides)
    return EnrichmentSourceRow(row_number=2, values=values)


def test_identity_stage_requires_full_exact_identity_and_is_idempotent(db_session):
    player = Player(name="Arch Manning", school="Texas", position="QB", sheet_projected_season_points=409.0, current_value_rating=91)
    db_session.add(player)
    db_session.commit()

    first = import_identities_and_bios(db_session, [source_row()], approved_aliases={}, apply=True)
    db_session.commit()

    assert first.exact == 1
    assert first.inserted == 1
    mapping = db_session.query(PlayerProviderId).one()
    assert mapping.player_id == player.id
    assert mapping.verification_status == "verified"
    refreshed = db_session.get(Player, player.id)
    assert refreshed.espn_height == "6' 4\""
    assert refreshed.sheet_projected_season_points == 409.0
    assert refreshed.current_value_rating == 91

    second = import_identities_and_bios(db_session, [source_row()], approved_aliases={}, apply=True)
    assert second.unchanged == 1
    assert db_session.query(PlayerProviderId).count() == 1


def test_identity_rejects_ambiguous_name_without_a_reviewed_alias(db_session):
    db_session.add_all([
        Player(name="Chris Johnson", school="Texas", position="RB"),
        Player(name="Chris Johnson", school="Texas", position="RB"),
    ])
    db_session.commit()

    result = resolve_identity(db_session, source_row(player_name="Chris Johnson", position="RB", provider_player_id="111"))

    assert result.outcome is MatchOutcome.AMBIGUOUS


def test_identity_marks_school_and_position_mismatches_for_review(db_session):
    db_session.add(Player(name="Arch Manning", school="Texas", position="QB"))
    db_session.commit()

    school = resolve_identity(db_session, source_row(school="Georgia", provider_player_id="112"))
    position = resolve_identity(db_session, source_row(position="WR", provider_player_id="113"))

    assert school.outcome is MatchOutcome.CONFLICT
    assert position.outcome is MatchOutcome.CONFLICT


def test_reviewed_alias_can_only_resolve_the_explicit_provider_id(db_session):
    player = Player(name="Arch Manning", school="Texas", position="QB")
    db_session.add(player)
    db_session.commit()

    result = resolve_identity(
        db_session,
        source_row(player_name="Archibald Manning", provider_player_id="114"),
        approved_aliases={("espn", "114"): player.id},
    )

    assert result.outcome is MatchOutcome.VERIFIED_ALIAS
    assert result.player_id == player.id


def test_historical_import_preserves_missing_fields_as_null(db_session):
    player = Player(name="Arch Manning", school="Texas", position="QB")
    db_session.add(player)
    db_session.commit()
    row = source_row(season="2025", historical_team="Texas", passing_yards="3828")

    report = import_historical_totals(db_session, [row], approved_aliases={}, apply=True, source_sha256="a" * 64)
    db_session.commit()

    assert report.inserted == 1
    stored = db_session.query(PlayerHistoricalSeasonStat).one()
    assert stored.passing_yards == 3828.0
    assert stored.receptions is None
    assert stored.fantasy_points is None


def test_game_logs_derive_from_team_schedule_without_copying_player_schedules(db_session):
    player = Player(name="Arch Manning", school="Texas", position="QB")
    db_session.add_all([
        player,
        TeamSchedule(
            team_name="Texas", season=2026, week=1, opponent_name="Ohio State", location="home",
            is_bye=False, game_date=date(2026, 9, 5), neutral_site=False, conference_game=False, date_confirmed=True,
        ),
    ])
    db_session.commit()

    game_log = build_player_game_log(db_session, player, season=2026)

    assert len(game_log.games) == 1
    assert game_log.games[0].opponent_name == "Ohio State"
    assert game_log.games[0].stats is None


def test_weekly_stage_rejects_incomplete_exports_instead_of_deriving_values(db_session):
    player = Player(name="Arch Manning", school="Texas", position="QB")
    db_session.add(player)
    db_session.commit()

    report = import_weekly_projections(
        db_session,
        [source_row(season="2026", week="1", projection_version="FINAL", opponent_team="Ohio State")],
        approved_aliases={},
        apply=False,
    )

    assert report.conflicts == 1
    assert report.inserted == 0
