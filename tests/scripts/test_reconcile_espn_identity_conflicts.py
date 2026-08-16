import pytest

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId, ProviderIdentityAudit
from collegefootballfantasy_api.app.services.provider_identity import ProviderIdentityConflict
from scripts.reconcile_espn_identity_conflicts import IdentityDecision, reconcile_decisions


def _decision(player_id: int, old_id: str, new_id: str, team_id: str = "127") -> IdentityDecision:
    return IdentityDecision(
        internal_player_id=player_id,
        expected_provider_player_id=old_id,
        replacement_provider_player_id=new_id,
        replacement_provider_team_id=team_id,
        evidence={"profile_sha256": "profile-hash", "roster_sha256": "roster-hash"},
    )


def test_reconciliation_replaces_only_exact_expected_mapping_and_preserves_audit(db_session):
    player = Player(name="Fredrick Moore", school="Michigan State", position="WR")
    db_session.add(player)
    db_session.flush()
    mapping = PlayerProviderId(
        player_id=player.id,
        provider="espn",
        provider_player_id="4905609",
        verification_status="verified",
        match_confidence=1.0,
    )
    db_session.add(mapping)
    db_session.flush()

    assert reconcile_decisions(db_session, [_decision(player.id, "4905609", "5332189")]) == 1

    assert mapping.id is not None
    assert mapping.provider_player_id == "5332189"
    assert mapping.provider_team_id == "127"
    assert mapping.verification_status == "verified"
    audit = db_session.query(ProviderIdentityAudit).filter_by(entity_id=mapping.id, action="replace_verified_mapping").one()
    assert audit.before_state["provider_player_id"] == "4905609"
    assert audit.after_state["provider_player_id"] == "5332189"
    assert audit.after_state["evidence"]["profile_sha256"] == "profile-hash"


def test_reconciliation_refuses_a_target_athlete_owned_by_another_player(db_session):
    first = Player(name="First", school="Michigan State", position="WR")
    second = Player(name="Second", school="Michigan State", position="WR")
    db_session.add_all([first, second])
    db_session.flush()
    db_session.add_all(
        [
            PlayerProviderId(player_id=first.id, provider="espn", provider_player_id="4905609", verification_status="verified"),
            PlayerProviderId(player_id=second.id, provider="espn", provider_player_id="5332189", verification_status="verified"),
        ]
    )
    db_session.flush()

    with pytest.raises(ProviderIdentityConflict, match="already owned"):
        reconcile_decisions(db_session, [_decision(first.id, "4905609", "5332189")])
