"""Read-only ESPN alpha readiness audit.

This intentionally reports gaps rather than guessing or writing provider
identities.  Run it against the exact database intended for shadow deployment
after the schedule/player import completes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school


def _school_key(value: str | None) -> str:
    return canonical_school_name(value or "") or normalize_school(value or "") or ""


def _numeric_provider_id(value: str | None) -> bool:
    return bool(value and str(value).strip().isdigit())


def _event_team_key(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("location") or value.get("shortDisplayName") or value.get("displayName") or value.get("name")
    return _school_key(str(value or ""))


def _event_kickoff(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _load_espn_events(event_fixture: Path | None) -> dict[str, tuple[set[str], datetime | None]] | None:
    """Load an explicitly captured ESPN scoreboard fixture; never query ESPN.

    Event IDs are considered verified only if the fixture confirms the same
    event, both participating schools, and (where our schedule has one) the
    exact kickoff instant.  Name-only matching is deliberately impossible.
    """

    if event_fixture is None:
        return None
    payload = json.loads(event_fixture.read_text(encoding="utf-8"))
    raw_events = payload.get("events", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_events, list):
        raise ValueError("ESPN event fixture must contain an events list")
    result: dict[str, tuple[set[str], datetime | None]] = {}
    for event in raw_events:
        if not isinstance(event, dict) or not _numeric_provider_id(str(event.get("id") or "")):
            continue
        competitions = event.get("competitions")
        competition = competitions[0] if isinstance(competitions, list) and competitions and isinstance(competitions[0], dict) else {}
        competitors = competition.get("competitors") if isinstance(competition, dict) else []
        teams = {_event_team_key((entry or {}).get("team")) for entry in competitors if isinstance(entry, dict)}
        teams.discard("")
        result[str(event["id"]).strip()] = (teams, _event_kickoff(event.get("date") or competition.get("date")))
    return result


def _game_matches_espn_event(game: Game, fixture_event: tuple[set[str], datetime | None]) -> bool:
    teams, kickoff = fixture_event
    if {_school_key(game.home_team), _school_key(game.away_team)} != teams:
        return False
    if game.start_date is None:
        return True
    game_kickoff = game.start_date.replace(tzinfo=timezone.utc) if game.start_date.tzinfo is None else game.start_date.astimezone(timezone.utc)
    return kickoff is not None and game_kickoff == kickoff


def build_readiness_report(db: Session, *, season: int, event_fixture: Path | None = None) -> dict:
    players = (
        db.query(Player.id, Player.name, Player.school, Player.position, Player.depth_chart_position)
        .filter(canonical_fantasy_player_filter(season))
        .order_by(Player.id.asc())
        .all()
    )
    player_ids = {player.id for player in players}
    mappings = (
        db.query(
            PlayerProviderId.player_id,
            PlayerProviderId.provider_player_id,
            PlayerProviderId.verification_status,
        )
        .filter(PlayerProviderId.provider == "espn", PlayerProviderId.player_id.in_(player_ids or {0}))
        .all()
    )
    mappings_by_player: dict[int, list] = defaultdict(list)
    for mapping in mappings:
        mappings_by_player[mapping.player_id].append(mapping)
    mapping_by_player = {
        player_id: entries[0]
        for player_id, entries in mappings_by_player.items()
        if len(entries) == 1
    }
    verified = [mapping for mapping in mappings if mapping.verification_status == "verified" and _numeric_provider_id(mapping.provider_player_id)]
    id_counts = Counter(mapping.provider_player_id.strip() for mapping in mappings if _numeric_provider_id(mapping.provider_player_id))
    missing_players = []
    for player in players:
        candidates = mappings_by_player.get(player.id, [])
        mapping = mapping_by_player.get(player.id)
        if not candidates:
            reason = "missing_espn_mapping"
        elif len(candidates) != 1:
            reason = "conflicting_espn_mappings"
        elif mapping.verification_status != "verified":
            reason = "espn_mapping_not_verified"
        elif not _numeric_provider_id(mapping.provider_player_id):
            reason = "invalid_espn_player_id"
        else:
            continue
        missing_players.append(
            {
                "player_id": player.id,
                "name": player.name,
                "school": player.school,
                "position": player.position,
                "depth_chart_position": player.depth_chart_position,
                "reason_unresolved": reason,
                "current_provider_mapping": (
                    {
                        "provider_player_id": mapping.provider_player_id,
                        "verification_status": mapping.verification_status,
                    }
                    if mapping is not None
                    else None
                ),
            }
        )
    invalid_mappings = [
        {"player_id": mapping.player_id, "provider_player_id": mapping.provider_player_id, "verification_status": mapping.verification_status}
        for mapping in mappings
        if not _numeric_provider_id(mapping.provider_player_id)
    ]
    duplicate_player_ids = sorted(provider_id for provider_id, count in id_counts.items() if count > 1)
    conflicting_player_ids = sorted(player_id for player_id, entries in mappings_by_player.items() if len(entries) > 1)

    school_keys = {_school_key(player.school) for player in players if _school_key(player.school)}
    relevant_games = [
        game
        for game in db.query(Game.id, Game.external_id, Game.week, Game.home_team, Game.away_team, Game.start_date, Game.schedule_status)
        .filter(Game.season == season)
        .order_by(Game.week.asc(), Game.id.asc())
        .all()
        if _school_key(game.home_team) in school_keys or _school_key(game.away_team) in school_keys
    ]
    game_id_counts = Counter(str(game.external_id).strip() for game in relevant_games if _numeric_provider_id(game.external_id))
    missing_games = [
        {"game_id": game.id, "week": game.week, "home_team": game.home_team, "away_team": game.away_team}
        for game in relevant_games
        if not _numeric_provider_id(game.external_id)
    ]
    tbd_kickoffs = [
        {"game_id": game.id, "week": game.week, "home_team": game.home_team, "away_team": game.away_team}
        for game in relevant_games
        if game.start_date is None or (game.schedule_status or "").lower() in {"tbd", "postponed", "cancelled", "canceled"}
    ]
    duplicate_event_ids = sorted(event_id for event_id, count in game_id_counts.items() if count > 1)
    espn_events = _load_espn_events(event_fixture)
    verified_games = []
    event_mismatches = []
    if espn_events is not None:
        for game in relevant_games:
            event = espn_events.get(str(game.external_id or "").strip())
            if event is not None and _game_matches_espn_event(game, event):
                verified_games.append(game)
            elif _numeric_provider_id(game.external_id):
                event_mismatches.append(
                    {"game_id": game.id, "external_id": game.external_id, "week": game.week, "home_team": game.home_team, "away_team": game.away_team, "reason_unresolved": "espn_event_home_away_or_kickoff_mismatch"}
                )

    return {
        "season": season,
        "players": {
            "total_rosterable_players": len(players),
            "verified_espn_player_ids": len(verified),
            "missing_espn_player_ids": len(missing_players),
            "duplicate_espn_player_ids": duplicate_player_ids,
            "conflicting_espn_player_ids": duplicate_player_ids,
            "conflicting_player_mappings": conflicting_player_ids,
            "invalid_espn_player_ids": invalid_mappings,
            "remediation_players": missing_players,
        },
        "games": {
            "total_relevant_games": len(relevant_games),
            # A numeric ID alone is a structural check, not proof that it is
            # the ESPN event for the stored participants and kickoff.
            "espn_event_crosscheck_available": espn_events is not None,
            "structurally_valid_espn_event_ids": sum(1 for game in relevant_games if _numeric_provider_id(game.external_id)),
            "verified_espn_event_ids": len(verified_games),
            "missing_espn_event_ids": len(missing_games),
            "duplicate_espn_event_ids": duplicate_event_ids,
            "conflicting_espn_event_ids": duplicate_event_ids,
            "tbd_kickoffs": len(tbd_kickoffs),
            "remediation_games": missing_games,
            "event_crosscheck_mismatches": event_mismatches,
            "tbd_games": tbd_kickoffs,
        },
    }


def render_readiness_markdown(report: dict) -> str:
    """Render a reviewable companion without changing the machine report."""

    players = report["players"]
    games = report["games"]
    player_total = players["total_rosterable_players"]
    game_total = games["total_relevant_games"]
    return "\n".join(
        [
            f"# ESPN live-scoring readiness — {report['season']}",
            "",
            "## Players",
            "",
            f"- Total rosterable players: {player_total}",
            f"- Verified ESPN IDs: {players['verified_espn_player_ids']}",
            f"- Missing/unresolved ESPN IDs: {players['missing_espn_player_ids']}",
            f"- Duplicate ESPN IDs: {len(players['duplicate_espn_player_ids'])}",
            f"- Invalid ESPN IDs: {len(players['invalid_espn_player_ids'])}",
            f"- Verified percentage: {(100 * players['verified_espn_player_ids'] / player_total) if player_total else 0:.2f}%",
            "",
            "## Games",
            "",
            f"- Total relevant games: {game_total}",
            f"- ESPN event cross-check fixture supplied: {'yes' if games['espn_event_crosscheck_available'] else 'no'}",
            f"- Verified ESPN event IDs: {games['verified_espn_event_ids']}",
            f"- Missing ESPN event IDs: {games['missing_espn_event_ids']}",
            f"- Duplicate ESPN event IDs: {len(games['duplicate_espn_event_ids'])}",
            f"- TBD/postponed/cancelled kickoffs: {games['tbd_kickoffs']}",
            f"- Verified percentage: {(100 * games['verified_espn_event_ids'] / game_total) if game_total else 0:.2f}%",
            "",
            "The JSON companion contains every unresolved player and game. Numeric event IDs are not treated as verified without a captured ESPN event fixture that matches ID, home team, away team, and kickoff.",
            "",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a read-only ESPN live-scoring readiness report.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--output", type=Path, help="Optional JSON report destination.")
    parser.add_argument("--markdown-output", type=Path, help="Optional human-readable Markdown companion.")
    parser.add_argument(
        "--event-fixture",
        type=Path,
        help="Sanitized captured ESPN scoreboard fixture used to verify event ID, home/away, and kickoff. No network request is made.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_models_registered()
    with SessionLocal() as db:
        revision = db.execute(text("select version_num from alembic_version")).scalar_one_or_none()
        if revision != "0101_injury_notification_scope":
            raise SystemExit(
                "Refusing readiness audit: database must be migrated to "
                "0101_injury_notification_scope before its player/game identity data can be certified."
            )
        report = build_readiness_report(db, season=args.season, event_fixture=args.event_fixture)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.write_text(render_readiness_markdown(report), encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
