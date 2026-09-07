from datetime import datetime, timedelta, timezone

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services.espn_player_lookup import ESPNIdentityResolution, ResolvedESPNPlayer
from collegefootballfantasy_api.app.services.espn_pregame_identity import reconcile_pregame_espn_identities
import collegefootballfantasy_api.app.services.espn_pregame_identity as pregame_identity


NOW = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)


def test_pregame_identity_reconciliation_promotes_only_exact_resolver_matches(db_session, monkeypatch):
    player = Player(name="Exact Match", school="Texas", position="WR")
    db_session.add_all([
        player,
        TeamSchedule(
            team_name="Texas",
            season=2026,
            week=2,
            opponent_name="Ohio State",
            location="home",
            is_bye=False,
            kickoff_at=NOW + timedelta(hours=2),
        ),
    ])
    db_session.commit()

    def resolve_exact(db, candidate, *, client):
        db.add(PlayerProviderId(
            player_id=candidate.id,
            provider="espn",
            provider_player_id="123",
            verification_status="legacy_backfill",
        ))
        db.commit()
        return ESPNIdentityResolution("matched", ResolvedESPNPlayer("123"))

    monkeypatch.setattr(pregame_identity, "resolve_espn_player_identity_and_profile", resolve_exact)

    result = reconcile_pregame_espn_identities(
        db_session,
        season=2026,
        week=2,
        client=object(),
        now=NOW,
        limit=1,
    )

    mapping = db_session.query(PlayerProviderId).filter_by(player_id=player.id, provider="espn").one()
    assert result == {"considered": 1, "verified": 1, "unresolved": 0}
    assert mapping.verification_status == "verified"
