from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from scripts.audit_espn_live_readiness import build_readiness_report


def test_readiness_audit_reports_only_verified_numeric_espn_identities_and_game_ids(db_session):
    ensure_models_registered()
    verified = Player(
        name="Verified QB",
        position="QB",
        school="Texas",
        sheet_source_sheet_id="canonical-preseason:2026:test",
        sheet_projected_season_points=200,
    )
    missing = Player(
        name="Missing WR",
        position="WR",
        school="Texas",
        sheet_source_sheet_id="canonical-preseason:2026:test",
        sheet_projected_season_points=100,
    )
    legacy = Player(
        name="Legacy RB",
        position="RB",
        school="Texas",
        sheet_source_sheet_id="canonical-preseason:2026:test",
        sheet_projected_season_points=100,
    )
    db_session.add_all([verified, missing, legacy])
    db_session.flush()
    db_session.add_all(
        [
            PlayerProviderId(player_id=verified.id, provider="espn", provider_player_id="123", verification_status="verified"),
            PlayerProviderId(player_id=legacy.id, provider="espn", provider_player_id="not-an-espn-id", verification_status="legacy_backfill"),
            Game(external_id="401000001", season=2026, week=1, home_team="Texas", away_team="Other"),
            Game(external_id=None, season=2026, week=2, home_team="Texas", away_team="Elsewhere"),
        ]
    )
    db_session.commit()

    report = build_readiness_report(db_session, season=2026)

    assert report["players"]["total_rosterable_players"] == 3
    assert report["players"]["verified_espn_player_ids"] == 1
    assert report["players"]["missing_espn_player_ids"] == 2
    assert len(report["players"]["invalid_espn_player_ids"]) == 1
    assert report["games"]["total_relevant_games"] == 2
    assert report["games"]["verified_espn_event_ids"] == 1
    assert report["games"]["missing_espn_event_ids"] == 1
    assert report["games"]["tbd_kickoffs"] == 2
