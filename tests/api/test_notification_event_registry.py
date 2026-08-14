from __future__ import annotations

import json

from collegefootballfantasy_api.app.services.notification_events import (
    NOTIFICATION_EVENTS,
    NotificationScope,
    canonical_event_type,
    get_notification_event,
    notification_event_contract,
)


def test_alpha_event_registry_is_machine_readable_and_complete() -> None:
    expected = {
        "DRAFT_1H", "DRAFT_START", "DRAFT_ON_CLOCK", "DRAFT_AUTO_PICK", "DRAFT_COMPLETED",
        "MATCHUP_START", "TRADE_RECEIVED", "TRADE_ACCEPTED_PENDING", "TRADE_COMPLETED",
        "TRADE_DECLINED", "TRADE_CANCELED", "TRADE_EXPIRED", "WAIVER_WON", "WAIVER_LOST",
        "MATCHUP_FINAL", "MATCHUP_CORRECTED", "BIG_PLAY",
    }
    assert expected <= set(NOTIFICATION_EVENTS)
    assert {definition.privacy_scope for definition in NOTIFICATION_EVENTS.values()} <= set(NotificationScope)
    assert json.loads(json.dumps(notification_event_contract()))["version"] == 1


def test_legacy_event_names_normalize_to_the_canonical_alpha_contract() -> None:
    assert canonical_event_type("trade_proposed") == "TRADE_RECEIVED"
    assert canonical_event_type("trade_accepted") == "TRADE_ACCEPTED_PENDING"
    assert canonical_event_type("trade_processed") == "TRADE_COMPLETED"
    assert canonical_event_type("waiver_processed") == "WAIVER_WON"
    assert get_notification_event("trade_cancelled").privacy_scope is NotificationScope.PRIVATE_TRADE_PARTICIPANT
