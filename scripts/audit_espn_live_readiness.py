"""Read-only ESPN alpha readiness audit.

This intentionally reports gaps rather than guessing or writing provider
identities.  Run it against the exact database intended for shadow deployment
after the schedule/player import completes.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
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


def build_readiness_report(db: Session, *, season: int) -> dict:
    players = (
        db.query(Player.id, Player.name, Player.school, Player.position)
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
    mapping_by_player = {mapping.player_id: mapping for mapping in mappings}
    verified = [mapping for mapping in mappings if mapping.verification_status == "verified" and _numeric_provider_id(mapping.provider_player_id)]
    id_counts = Counter(mapping.provider_player_id.strip() for mapping in mappings if _numeric_provider_id(mapping.provider_player_id))
    missing_players = [
        {"player_id": player.id, "name": player.name, "school": player.school, "position": player.position}
        for player in players
        if player.id not in mapping_by_player
        or mapping_by_player[player.id].verification_status != "verified"
        or not _numeric_provider_id(mapping_by_player[player.id].provider_player_id)
    ]
    invalid_mappings = [
        {"player_id": mapping.player_id, "provider_player_id": mapping.provider_player_id, "verification_status": mapping.verification_status}
        for mapping in mappings
        if not _numeric_provider_id(mapping.provider_player_id)
    ]
    duplicate_player_ids = sorted(provider_id for provider_id, count in id_counts.items() if count > 1)

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

    return {
        "season": season,
        "players": {
            "total_rosterable_players": len(players),
            "verified_espn_player_ids": len(verified),
            "missing_espn_player_ids": len(missing_players),
            "duplicate_espn_player_ids": duplicate_player_ids,
            "conflicting_espn_player_ids": duplicate_player_ids,
            "invalid_espn_player_ids": invalid_mappings,
            "remediation_players": missing_players,
        },
        "games": {
            "total_relevant_games": len(relevant_games),
            "verified_espn_event_ids": sum(1 for game in relevant_games if _numeric_provider_id(game.external_id)),
            "missing_espn_event_ids": len(missing_games),
            "duplicate_espn_event_ids": duplicate_event_ids,
            "conflicting_espn_event_ids": duplicate_event_ids,
            "tbd_kickoffs": len(tbd_kickoffs),
            "remediation_games": missing_games,
            "tbd_games": tbd_kickoffs,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a read-only ESPN live-scoring readiness report.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--output", type=Path, help="Optional JSON report destination.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_models_registered()
    with SessionLocal() as db:
        revision = db.execute(text("select version_num from alembic_version")).scalar_one_or_none()
        if revision != "0092_espn_shadow_game_polls":
            raise SystemExit(
                "Refusing readiness audit: database must be migrated to "
                "0092_espn_shadow_game_polls before its player/game identity data can be certified."
            )
        report = build_readiness_report(db, season=args.season)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
