from __future__ import annotations

import json

import pytest

from collegefootballfantasy_api.app.services.notification_events import (
    NOTIFICATION_EVENTS,
    NotificationScope,
    canonical_event_type,
    get_notification_event,
    notification_event_contract,
    render_event_content,
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


@pytest.mark.parametrize(
    ("event_type", "payload", "expected_title", "expected_body"),
    [
        ("DRAFT_1H", {"localized_draft_time": "Aug 28 at 7:00 PM EDT"}, "Your draft starts in 1 hour", "Alpha League begins at Aug 28 at 7:00 PM EDT."),
        ("DRAFT_SOON", {"local_draft_time": "Aug 28 at 7:00 PM EDT"}, "Your draft starts soon", "Alpha League begins at Aug 28 at 7:00 PM EDT."),
        ("DRAFT_START", {}, "Your draft is starting", "Enter the Alpha League draft room now."),
        ("DRAFT_ON_CLOCK", {"round_number": 4}, "You’re on the clock", "Make your Round 4 pick in Alpha League."),
        ("DRAFT_AUTO_PICK", {"player_name": "Avery Player", "round": 6}, "Your pick was made automatically", "Avery Player was selected for you in Round 6."),
        ("DRAFT_COMPLETED", {}, "Your draft is complete", "Your Alpha League roster is ready."),
        ("MATCHUP_START", {"week": 3, "opponent_team_name": "Rival Team"}, "Your matchup is underway", "Your Week 3 matchup against Rival Team has started."),
        ("MATCHUP_FINAL", {"outcome": "won", "opponent_team": "Rival Team", "user_score": 31, "opponent_score": 28}, "Matchup won", "You defeated Rival Team, 31–28."),
        ("MATCHUP_FINAL", {"outcome": "lost", "opponent_team": "Rival Team", "user_score": 28, "opponent_score": 31}, "Matchup final", "Rival Team defeated your team, 31–28."),
        ("MATCHUP_FINAL", {"outcome": "tied", "opponent_team": "Rival Team", "user_score": 28, "opponent_score": 28}, "Matchup tied", "Your matchup with Rival Team ended 28–28."),
        ("MATCHUP_CORRECTED", {"week": 3}, "Matchup result updated", "A stat correction changed your Week 3 matchup result."),
        ("TRADE_RECEIVED", {"manager_or_team": "Rival Team"}, "New trade offer", "Rival Team sent you a trade offer in Alpha League."),
        ("TRADE_ACCEPTED_PENDING", {}, "Trade accepted", "The trade will process when the involved players are eligible."),
        ("TRADE_COMPLETED", {}, "Trade completed", "Your trade in Alpha League has been processed."),
        ("TRADE_DECLINED", {}, "Trade declined", "Your trade offer in Alpha League was declined."),
        ("TRADE_CANCELED", {}, "Trade canceled", "The trade offer in Alpha League was canceled."),
        ("TRADE_EXPIRED", {}, "Trade expired", "The trade offer in Alpha League expired."),
        ("WAIVER_WON", {"player_name": "Avery Player"}, "Waiver claim successful", "You added Avery Player in Alpha League."),
        ("WAIVER_LOST", {"player_name": "Avery Player"}, "Waiver claim unsuccessful", "Your claim for Avery Player was not awarded."),
        ("WAIVER_FAILED", {}, "Waiver claim could not process", "Review your roster or waiver settings in Alpha League."),
    ],
)
def test_approved_notification_copy_snapshots(
    event_type: str,
    payload: dict,
    expected_title: str,
    expected_body: str,
) -> None:
    _category, title, body = render_event_content(event_type, payload, "Alpha League")
    assert (title, body) == (expected_title, expected_body)


def test_notification_copy_uses_safe_fallbacks_for_missing_optional_variables() -> None:
    assert render_event_content("DRAFT_1H", {}, "")[1:] == (
        "Your draft starts in 1 hour",
        "your league begins at the scheduled time.",
    )
    assert render_event_content("DRAFT_AUTO_PICK", {}, "Alpha League")[1:] == (
        "Your pick was made automatically",
        "a player was selected for you in Round next.",
    )
    assert render_event_content("WAIVER_LOST", {}, "Alpha League")[1:] == (
        "Waiver claim unsuccessful",
        "Your claim for a player was not awarded.",
    )
    assert render_event_content("MATCHUP_START", {}, "Alpha League")[1:] == (
        "Your matchup is underway",
        "Your matchup against your opponent has started.",
    )
    assert render_event_content("MATCHUP_FINAL", {"outcome": "won"}, "Alpha League")[1:] == (
        "Matchup final",
        "Your matchup is final.",
    )
    assert render_event_content("MATCHUP_CORRECTED", {}, "Alpha League")[1:] == (
        "Matchup result updated",
        "A stat correction changed your matchup result.",
    )


def test_notification_copy_bounds_long_user_supplied_variables() -> None:
    long_name = "A" * 200
    _category, _title, body = render_event_content(
        "TRADE_RECEIVED",
        {"manager_or_team": long_name},
        long_name,
    )
    shortened = f"{'A' * 79}…"
    assert body == f"{shortened} sent you a trade offer in {shortened}."
    assert long_name not in body


def test_notification_copy_escapes_html_in_user_supplied_names() -> None:
    injected = "<img src=x onerror=alert(1)>"
    _category, _title, body = render_event_content(
        "TRADE_RECEIVED",
        {"manager_or_team": injected},
        injected,
    )
    assert "<img" not in body
    assert "onerror=" in body
    assert "&lt;img src=x onerror=alert(1)&gt;" in body
