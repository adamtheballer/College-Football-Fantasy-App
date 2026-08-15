"""Canonical notification event contract.

The outbox stores an event type, but all product semantics live here rather
than being reimplemented by individual producers.  This is deliberately a
plain, serializable Python contract: tests can validate it directly and tools
can export :func:`notification_event_contract` without a second hand-written
JSON registry drifting from delivery behaviour.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from html import escape
from typing import Any


class NotificationScope(str, Enum):
    """Authorization purpose recorded with a durable event.

    Visibility is still enforced by the immutable recipient user ID in the
    notification log.  Scope is not an authorization bypass or a payload-only
    visibility rule.
    """

    DIRECT_USER = "direct_user"
    LEAGUE_MEMBER = "league_member"
    MATCHUP_PARTICIPANT = "matchup_participant"
    PRIVATE_TRADE_PARTICIPANT = "private_trade_participant"
    SYSTEM = "system"


@dataclass(frozen=True)
class NotificationEventDefinition:
    event_type: str
    category: str
    producer: str
    recipient_rule: str
    required_source_state: str
    in_app_title: str
    in_app_body: str
    push_title: str
    push_body: str
    destination_type: str
    idempotency_key_format: str
    global_preference: str | None
    league_preference: str | None
    quiet_hours_apply: bool
    time_critical: bool
    privacy_scope: NotificationScope


def _event(
    event_type: str,
    category: str,
    producer: str,
    recipient_rule: str,
    required_source_state: str,
    title: str,
    body: str,
    destination_type: str,
    idempotency_key_format: str,
    global_preference: str | None,
    league_preference: str | None,
    *,
    quiet_hours_apply: bool = True,
    time_critical: bool = False,
    privacy_scope: NotificationScope = NotificationScope.DIRECT_USER,
) -> NotificationEventDefinition:
    if time_critical:
        quiet_hours_apply = False
    return NotificationEventDefinition(
        event_type=event_type,
        category=category,
        producer=producer,
        recipient_rule=recipient_rule,
        required_source_state=required_source_state,
        in_app_title=title,
        in_app_body=body,
        push_title=title,
        push_body=body,
        destination_type=destination_type,
        idempotency_key_format=idempotency_key_format,
        global_preference=global_preference,
        league_preference=league_preference,
        quiet_hours_apply=quiet_hours_apply,
        time_critical=time_critical,
        privacy_scope=privacy_scope,
    )


# The alpha event matrix.  Every producer must enqueue one of these events;
# gameplay services never call providers directly.
NOTIFICATION_EVENTS: dict[str, NotificationEventDefinition] = {
    "DRAFT_1H": _event(
        "DRAFT_1H", "DRAFT", "draft scheduling", "each eligible human manager",
        "official scheduled draft at least one hour away", "Your draft starts in 1 hour",
        "{league_name} begins at {local_draft_time}.", "draft",
        "draft_1h:{draft_id}:{schedule_revision}:{recipient_user_id}", "draft_alerts", "draft_alerts",
        time_critical=True,
    ),
    "DRAFT_SOON": _event(
        "DRAFT_SOON", "DRAFT", "draft scheduling", "each eligible human manager",
        "official draft scheduled less than one hour away", "Your draft starts soon",
        "{league_name} begins at {local_draft_time}.", "draft",
        "draft_soon:{draft_id}:{schedule_revision}:{recipient_user_id}", "draft_alerts", "draft_alerts",
        time_critical=True,
    ),
    "DRAFT_START": _event(
        "DRAFT_START", "DRAFT", "draft state transition", "each eligible human manager",
        "draft entered on_clock", "Your draft is starting", "Enter the {league_name} draft room now.", "draft",
        "draft_start:{draft_id}:{recipient_user_id}", "draft_alerts", "draft_alerts", time_critical=True,
    ),
    "DRAFT_ON_CLOCK": _event(
        "DRAFT_ON_CLOCK", "DRAFT", "draft pick transition", "current human manager only",
        "official on_clock turn", "You’re on the clock", "Make your Round {round} pick in {league_name}.", "draft",
        "draft_on_clock:{draft_id}:{overall_pick}:{recipient_user_id}", "draft_alerts", "draft_alerts", time_critical=True,
    ),
    "DRAFT_AUTO_PICK": _event(
        "DRAFT_AUTO_PICK", "DRAFT", "draft pick transaction", "affected human manager only",
        "auto-pick and roster mutation committed", "Your pick was made automatically",
        "{player_name} was selected for you in Round {round}.", "draft",
        "draft_autopick:{draft_id}:{draft_pick_id}:{recipient_user_id}", "draft_alerts", "draft_alerts", time_critical=True,
    ),
    "DRAFT_COMPLETED": _event(
        "DRAFT_COMPLETED", "DRAFT", "draft completion", "each eligible human manager",
        "official draft and roster finalization committed", "Your draft is complete",
        "Your {league_name} roster is ready.", "league",
        "draft_complete:{draft_id}:{recipient_user_id}", "draft_alerts", "draft_alerts",
    ),
    "MATCHUP_START": _event(
        "MATCHUP_START", "MATCHUP", "lineup snapshot scheduler", "each human matchup participant",
        "earliest verified eligible starter kickoff", "Your matchup is underway",
        "Your Week {week} matchup against {opponent_team} has started.", "matchup",
        "matchup_start:{matchup_id}:{recipient_user_id}", "matchup_start_alerts", "matchup_start_alerts",
        privacy_scope=NotificationScope.MATCHUP_PARTICIPANT,
    ),
    "TRADE_RECEIVED": _event(
        "TRADE_RECEIVED", "TRADE", "trade creation", "receiving manager only",
        "trade offer committed", "New trade offer", "{manager_or_team} sent you a trade offer in {league_name}.", "trade",
        "trade_received:{trade_id}:{recipient_user_id}", "trade_alerts", "trade_alerts",
        privacy_scope=NotificationScope.PRIVATE_TRADE_PARTICIPANT,
    ),
    "TRADE_ACCEPTED_PENDING": _event(
        "TRADE_ACCEPTED_PENDING", "TRADE", "trade acceptance", "trade participants only",
        "accepted while roster movement is deferred", "Trade accepted",
        "The trade will process when the involved players are eligible.", "trade",
        "trade_accepted_pending:{trade_id}:{recipient_user_id}", "trade_alerts", "trade_alerts",
        privacy_scope=NotificationScope.PRIVATE_TRADE_PARTICIPANT,
    ),
    "TRADE_COMPLETED": _event(
        "TRADE_COMPLETED", "TRADE", "trade processor", "trade participants only",
        "player transfer committed", "Trade completed", "Your trade in {league_name} has been processed.", "trade",
        "trade_completed:{trade_id}:{recipient_user_id}", "trade_alerts", "trade_alerts",
        privacy_scope=NotificationScope.PRIVATE_TRADE_PARTICIPANT,
    ),
    "TRADE_DECLINED": _event(
        "TRADE_DECLINED", "TRADE", "trade action", "trade participants only", "trade declined", "Trade declined",
        "Your trade offer in {league_name} was declined.", "trade", "trade_declined:{trade_id}:{recipient_user_id}",
        "trade_alerts", "trade_alerts", privacy_scope=NotificationScope.PRIVATE_TRADE_PARTICIPANT,
    ),
    "TRADE_CANCELED": _event(
        "TRADE_CANCELED", "TRADE", "trade action", "trade participants only", "trade canceled", "Trade canceled",
        "The trade offer in {league_name} was canceled.", "trade", "trade_canceled:{trade_id}:{recipient_user_id}",
        "trade_alerts", "trade_alerts", privacy_scope=NotificationScope.PRIVATE_TRADE_PARTICIPANT,
    ),
    "TRADE_EXPIRED": _event(
        "TRADE_EXPIRED", "TRADE", "trade expiry worker", "trade participants only", "trade expired", "Trade expired",
        "The trade offer in {league_name} expired.", "trade", "trade_expired:{trade_id}:{recipient_user_id}",
        "trade_alerts", "trade_alerts", privacy_scope=NotificationScope.PRIVATE_TRADE_PARTICIPANT,
    ),
    "WAIVER_WON": _event(
        "WAIVER_WON", "WAIVER", "waiver processor", "claim owner only",
        "roster mutation and priority or FAAB transaction committed", "Waiver claim successful", "You added {player_name} in {league_name}.", "waivers",
        "waiver_won:{waiver_claim_id}:{recipient_user_id}", "waiver_alerts", "waiver_alerts", time_critical=True,
    ),
    "WAIVER_LOST": _event(
        "WAIVER_LOST", "WAIVER", "waiver processor", "claim owner only when league policy enables loser notices",
        "claim was not awarded", "Waiver claim unsuccessful", "Your claim for {player_name} was not awarded.", "waivers",
        "waiver_lost:{waiver_claim_id}:{recipient_user_id}", "waiver_alerts", "waiver_alerts",
    ),
    "MATCHUP_FINAL": _event(
        "MATCHUP_FINAL", "MATCHUP", "certified scoring finalizer", "each human matchup participant",
        "matchup status certified final", "Matchup final", "Your Week {week} matchup is final.", "matchup",
        "matchup_final:{matchup_id}:{recipient_user_id}:{final_revision}", "matchup_result_alerts", "matchup_result_alerts",
        privacy_scope=NotificationScope.MATCHUP_PARTICIPANT,
    ),
    "MATCHUP_CORRECTED": _event(
        "MATCHUP_CORRECTED", "MATCHUP", "certified scoring finalizer", "each human matchup participant",
        "certified result revision after stat correction", "Matchup result updated", "A stat correction changed your Week {week} matchup result.", "matchup",
        "matchup_corrected:{matchup_id}:{recipient_user_id}:{correction_revision}", "matchup_result_alerts", "matchup_result_alerts",
        privacy_scope=NotificationScope.MATCHUP_PARTICIPANT,
    ),
    "LINEUP_REMINDER": _event(
        "LINEUP_REMINDER", "MATCHUP", "lineup scheduler", "eligible human manager", "verified upcoming starter kickoff",
        "Set your lineup", "Your Week {week} matchup starts soon.", "matchup",
        "lineup_reminder:{matchup_id}:{recipient_user_id}:{kickoff_revision}", "lineup_reminders", "lineup_reminders",
    ),
    "BIG_PLAY": _event(
        "BIG_PLAY", "PLAYER", "canonical live-play intake", "eligible subscribed roster manager",
        "canonical provider play event and production flag enabled", "Player update", "{player_name} made a big play.", "league",
        "big_play:{provider}:{provider_game_id}:{provider_play_id}:{recipient_user_id}", "big_play_alerts", "big_play_alerts",
        privacy_scope=NotificationScope.LEAGUE_MEMBER,
    ),
    "TOUCHDOWN": _event(
        "TOUCHDOWN", "PLAYER", "canonical live-play intake", "eligible subscribed roster manager",
        "canonical provider touchdown event and production flag enabled", "Player scoring update", "{player_name} scored a touchdown.", "league",
        "big_play:{provider}:{provider_game_id}:{provider_play_id}:{recipient_user_id}", "touchdown_alerts", "touchdown_alerts",
        privacy_scope=NotificationScope.LEAGUE_MEMBER,
    ),
    "LONG_RUSH": _event(
        "LONG_RUSH", "PLAYER", "canonical live-play intake", "eligible subscribed roster manager",
        "canonical provider rush event and production flag enabled", "Long rush", "{player_name} had a long rushing play.", "league",
        "big_play:{provider}:{provider_game_id}:{provider_play_id}:{recipient_user_id}", "long_rush_alerts", "long_rush_alerts",
        privacy_scope=NotificationScope.LEAGUE_MEMBER,
    ),
    "LONG_RECEPTION": _event(
        "LONG_RECEPTION", "PLAYER", "canonical live-play intake", "eligible subscribed roster manager",
        "canonical provider reception event and production flag enabled", "Long reception", "{player_name} had a long reception.", "league",
        "big_play:{provider}:{provider_game_id}:{provider_play_id}:{recipient_user_id}", "long_reception_alerts", "long_reception_alerts",
        privacy_scope=NotificationScope.LEAGUE_MEMBER,
    ),
    "LONG_PASS": _event(
        "LONG_PASS", "PLAYER", "canonical live-play intake", "eligible subscribed roster manager",
        "canonical provider pass event and production flag enabled", "Long pass", "{player_name} had a long passing play.", "league",
        "big_play:{provider}:{provider_game_id}:{provider_play_id}:{recipient_user_id}", "long_pass_alerts", "long_pass_alerts",
        privacy_scope=NotificationScope.LEAGUE_MEMBER,
    ),
    "CHAT_DIRECT_MESSAGE": _event(
        "CHAT_DIRECT_MESSAGE", "CHAT", "private chat service", "private chat recipient only", "message committed", "New direct message",
        "You have a new direct message.", "chat", "chat_direct_message:{thread_id}:{recipient_user_id}", "chat_alerts", None,
        privacy_scope=NotificationScope.DIRECT_USER,
    ),
    # Compatibility events remain explicit so older producer paths cannot
    # bypass the registry while the alpha matrix is deployed.
    "DRAFT_RESCHEDULED": _event(
        "DRAFT_RESCHEDULED", "DRAFT", "draft scheduling", "each eligible human manager", "official draft rescheduled",
        "Draft rescheduled", "Your league draft time was updated.", "draft",
        "draft_rescheduled:{draft_id}:{schedule_revision}:{recipient_user_id}", "draft_alerts", "draft_alerts",
    ),
    "TRADE_COUNTERED": _event(
        "TRADE_COUNTERED", "TRADE", "trade action", "trade participants only", "counter offer committed",
        "Trade countered", "A replacement trade offer was sent.", "trade",
        "trade_countered:{trade_id}:{recipient_user_id}", "trade_alerts", "trade_alerts",
        privacy_scope=NotificationScope.PRIVATE_TRADE_PARTICIPANT,
    ),
    "TRADE_VETOED": _event(
        "TRADE_VETOED", "TRADE", "trade review", "trade participants only", "trade veto committed",
        "Trade vetoed", "A trade offer was vetoed.", "trade",
        "trade_vetoed:{trade_id}:{recipient_user_id}", "trade_alerts", "trade_alerts",
        privacy_scope=NotificationScope.PRIVATE_TRADE_PARTICIPANT,
    ),
    "TRADE_FAILED": _event(
        "TRADE_FAILED", "TRADE", "trade processor", "trade participants only", "trade processing failed",
        "Trade failed", "A trade could not be completed.", "trade",
        "trade_failed:{trade_id}:{recipient_user_id}", "trade_alerts", "trade_alerts",
        privacy_scope=NotificationScope.PRIVATE_TRADE_PARTICIPANT,
    ),
    "WAIVER_SUBMITTED": _event(
        "WAIVER_SUBMITTED", "WAIVER", "waiver service", "claim owner only", "claim committed",
        "Waiver claim submitted", "Your waiver claim was submitted.", "waivers",
        "waiver_submitted:{waiver_claim_id}:{recipient_user_id}", "waiver_alerts", "waiver_alerts",
    ),
    "WAIVER_CANCELED": _event(
        "WAIVER_CANCELED", "WAIVER", "waiver service", "claim owner only", "claim canceled",
        "Waiver claim canceled", "Your pending waiver claim was canceled.", "waivers",
        "waiver_canceled:{waiver_claim_id}:{recipient_user_id}", "waiver_alerts", "waiver_alerts",
    ),
    "WAIVER_FAILED": _event(
        "WAIVER_FAILED", "WAIVER", "waiver processor", "claim owner only", "claim terminalized as invalid or failed",
        "Waiver claim could not process", "Review your roster or waiver settings in {league_name}.", "waivers",
        "waiver_failed:{waiver_claim_id}:{recipient_user_id}", "waiver_alerts", "waiver_alerts",
    ),
    "FREE_AGENT_ADDED": _event(
        "FREE_AGENT_ADDED", "WAIVER", "roster transaction", "affected manager only", "roster mutation committed",
        "Free agent added", "A player was added to your roster.", "waivers",
        "free_agent_added:{transaction_id}:{recipient_user_id}", "waiver_alerts", "waiver_alerts",
    ),
    "INJURY": _event(
        "INJURY", "PLAYER", "legacy player feed", "eligible roster manager", "legacy feed event", "Player injury update",
        "A rostered player has an injury update.", "league", "injury:{event_id}:{recipient_user_id}", "injury_alerts", "injury_alerts",
        privacy_scope=NotificationScope.LEAGUE_MEMBER,
    ),
    "USAGE": _event(
        "USAGE", "PLAYER", "legacy player feed", "eligible roster manager", "legacy feed event", "Player usage update",
        "A rostered player has a usage update.", "league", "usage:{event_id}:{recipient_user_id}", "usage_alerts", "usage_alerts",
        privacy_scope=NotificationScope.LEAGUE_MEMBER,
    ),
    "PROJECTION": _event(
        "PROJECTION", "PLAYER", "legacy player feed", "eligible roster manager", "legacy feed event", "Projection update",
        "A rostered player projection changed.", "league", "projection:{event_id}:{recipient_user_id}", "projection_alerts", "projection_alerts",
        privacy_scope=NotificationScope.LEAGUE_MEMBER,
    ),
}


# Existing database rows and producer calls are normalized at the outbox
# boundary.  These aliases make the semantic upgrade backwards compatible
# while preventing newly-created records from perpetuating ambiguous names.
EVENT_TYPE_ALIASES = {
    "TRADE_PROPOSED": "TRADE_RECEIVED",
    "TRADE_ACCEPTED": "TRADE_ACCEPTED_PENDING",
    "TRADE_APPROVED": "TRADE_ACCEPTED_PENDING",
    "TRADE_PROCESSED": "TRADE_COMPLETED",
    "TRADE_REJECTED": "TRADE_DECLINED",
    "TRADE_CANCELLED": "TRADE_CANCELED",
    "WAIVER_PROCESSED": "WAIVER_WON",
    "WAIVER_CANCELLED": "WAIVER_CANCELED",
}


def canonical_event_type(value: str) -> str:
    normalized = value.strip().upper()
    return EVENT_TYPE_ALIASES.get(normalized, normalized)


def get_notification_event(value: str) -> NotificationEventDefinition:
    canonical = canonical_event_type(value)
    try:
        return NOTIFICATION_EVENTS[canonical]
    except KeyError as exc:
        raise ValueError(f"unsupported notification event type: {canonical}") from exc


_MAX_TEMPLATE_VALUE_LENGTH = 80


def _safe_template_value(value: Any, fallback: str) -> str:
    """Render a short plain-text value without allowing markup into notification copy."""

    if value is None:
        return fallback
    rendered = str(value).strip()
    if not rendered:
        return fallback
    if len(rendered) > _MAX_TEMPLATE_VALUE_LENGTH:
        rendered = f"{rendered[:_MAX_TEMPLATE_VALUE_LENGTH - 1].rstrip()}…"
    return escape(rendered, quote=False)


def _safe_score(value: Any) -> str | None:
    """Return a display score only when the producer supplied a real number."""

    if isinstance(value, bool) or value is None:
        return None
    try:
        return f"{float(value):g}"
    except (TypeError, ValueError):
        return None


def _render_matchup_final(payload: dict[str, Any]) -> tuple[str, str]:
    """Keep final-result wording truthful when an optional score is unavailable."""

    opponent = _safe_template_value(
        payload.get("opponent_team", payload.get("opponent_team_name")),
        "your opponent",
    )
    user_score = _safe_score(payload.get("user_score"))
    opponent_score = _safe_score(payload.get("opponent_score"))
    outcome = str(payload.get("outcome") or "").strip().lower()
    if user_score is None or opponent_score is None or outcome not in {"won", "lost", "tied"}:
        week = _safe_template_value(payload.get("week"), "")
        return (
            "Matchup final",
            f"Your Week {week} matchup is final." if week else "Your matchup is final.",
        )
    if outcome == "won":
        return "Matchup won", f"You defeated {opponent}, {user_score}–{opponent_score}."
    if outcome == "lost":
        return "Matchup final", f"{opponent} defeated your team, {opponent_score}–{user_score}."
    return "Matchup tied", f"Your matchup with {opponent} ended {user_score}–{opponent_score}."


def render_event_content(event_type: str, payload: dict[str, Any], league_name: str) -> tuple[str, str, str]:
    """Render approved, bounded plain-text copy from the event registry.

    All user-controlled league, manager, team, and player values are escaped
    here once before either the in-app log, push provider, or email provider
    receives them. Producers retain responsibility only for durable event
    facts; they never need to duplicate presentation copy.
    """

    definition = get_notification_event(event_type)
    context = {
        "league_name": _safe_template_value(league_name, "your league"),
        "local_draft_time": _safe_template_value(
            payload.get("local_draft_time", payload.get("localized_draft_time")),
            "the scheduled time",
        ),
        "round": _safe_template_value(payload.get("round", payload.get("round_number")), "next"),
        "player_name": _safe_template_value(payload.get("player_name"), "a player"),
        "manager_or_team": _safe_template_value(
            payload.get("manager_or_team", payload.get("actor_name")),
            "A manager",
        ),
        "week": _safe_template_value(payload.get("week"), "this"),
        "opponent_team": _safe_template_value(
            payload.get("opponent_team", payload.get("opponent_team_name")),
            "your opponent",
        ),
    }
    canonical = canonical_event_type(event_type)
    if canonical == "MATCHUP_FINAL":
        title, body = _render_matchup_final(payload)
        return definition.category, title, body
    if canonical == "MATCHUP_START" and not str(payload.get("week") or "").strip():
        return (
            definition.category,
            definition.in_app_title,
            f"Your matchup against {context['opponent_team']} has started.",
        )
    if canonical == "MATCHUP_CORRECTED" and "week" not in payload:
        return definition.category, definition.in_app_title, "A stat correction changed your matchup result."
    return (
        definition.category,
        definition.in_app_title.format(**context),
        definition.in_app_body.format(**context),
    )


def destination_for_event(event_type: str, *, league_id: int | None, payload: dict[str, Any]) -> dict[str, Any] | None:
    definition = get_notification_event(event_type)
    destination: dict[str, Any] = {"type": definition.destination_type, "league_id": league_id}
    resource_id = payload.get("trade_id") if definition.destination_type == "trade" else payload.get("thread_id")
    if resource_id is not None:
        destination["resource_id"] = resource_id
    if definition.destination_type == "matchup" and payload.get("matchup_id") is not None:
        destination["resource_id"] = payload["matchup_id"]
    return destination


def notification_event_contract() -> dict[str, Any]:
    """Return the machine-readable product contract used by tests and tooling."""

    return {
        "version": 1,
        "events": [
            {**asdict(definition), "privacy_scope": definition.privacy_scope.value}
            for _event_type, definition in sorted(NOTIFICATION_EVENTS.items())
        ],
    }
