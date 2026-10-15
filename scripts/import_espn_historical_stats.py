from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from typing import NamedTuple

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.models import league, roster, team, user
from collegefootballfantasy_api.app.models.historical_stats import HistoricalStatImportRun
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.espn_player_lookup import (
    persist_espn_player_profile,
    resolve_espn_player_identity_and_profile,
)
from collegefootballfantasy_api.app.services.historical_stats import (
    fetch_and_store_player_history,
    resolve_espn_player_id,
)
from collegefootballfantasy_api.app.services.provider_identity import record_unmatched_provider_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import ESPN historical player season stats into the local cache.")
    parser.add_argument("--player-id", type=int, action="append", dest="player_ids", help="Import one player ID. Repeatable.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of players to resolve and import.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report existing mappings and players needing safe ESPN identity resolution; do not call ESPN or write rows.",
    )
    parser.add_argument(
        "--skip-identity-resolution",
        action="store_true",
        help="Import only players with an existing trusted ESPN identity mapping.",
    )
    parser.add_argument(
        "--ignore-feature-flag",
        action="store_true",
        help="Allow imports even when ESPN_HISTORICAL_STATS_ENABLED is false.",
    )
    parser.add_argument("--game-log-season", type=int, action="append", dest="game_log_seasons", help="Also import verified per-game history for this season. Repeatable; remains independent of live league scores.")
    return parser.parse_args()


class IdentityResolutionResult(NamedTuple):
    mapped_players: list[Player]
    scanned: int
    already_mapped: int
    newly_mapped: int
    ambiguous: int
    not_found: int
    profile_rows_updated: int
    unmatched: int
    failed: int


def record_identity_outcome(db, player: Player, outcome: str, detail: str | None) -> None:
    record_unmatched_provider_row(
        db,
        provider="espn",
        feed=f"player_identity_{outcome}",
        row={"PlayerName": player.name, "School": player.school, "Position": player.position},
        reason=detail or f"ESPN player identity lookup {outcome}.",
    )
    db.commit()


def resolve_players_for_import(
    db,
    players: list[Player],
    *,
    resolve_missing: bool,
    dry_run: bool,
) -> IdentityResolutionResult:
    """Return players with trusted ESPN IDs, resolving missing identities when enabled.

    The resolver only persists exact name, school, and position matches. It is deliberately
    part of the import path so a fresh database does not require a separate manual identity
    bootstrap step before it can import historical stats.
    """

    mapped_players: list[Player] = []
    already_mapped = newly_mapped = ambiguous = not_found = profile_rows_updated = unmatched = failed = 0
    client = ESPNClient() if not dry_run else None
    requests_per_second = max(settings.espn_historical_stats_requests_per_second, 0.1)
    delay_seconds = 1 / requests_per_second

    for player in players:
        provider_player_id = resolve_espn_player_id(db, player)
        if provider_player_id:
            mapped_players.append(player)
            already_mapped += 1
            if not dry_run:
                try:
                    profile_payload = client.get_athlete_profile(provider_player_id)
                    if persist_espn_player_profile(player, profile_payload):
                        profile_rows_updated += 1
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    failed += 1
                    print(f"Could not enrich ESPN profile for player {player.id} ({player.name}): {exc}")
                time.sleep(delay_seconds)
            continue

        if dry_run or not resolve_missing:
            unmatched += 1
            continue

        try:
            identity = resolve_espn_player_identity_and_profile(db, player, client=client)
        except Exception as exc:
            failed += 1
            print(f"Could not resolve ESPN identity for player {player.id} ({player.name}): {exc}")
        else:
            if identity.outcome == "matched" and identity.resolved:
                mapped_players.append(player)
                newly_mapped += 1
                if identity.profile_updated:
                    profile_rows_updated += 1
            elif identity.outcome == "ambiguous":
                ambiguous += 1
                record_identity_outcome(db, player, identity.outcome, identity.detail)
            else:
                unmatched += 1
                not_found += 1
                record_identity_outcome(db, player, identity.outcome, identity.detail)

        time.sleep(delay_seconds)

    return IdentityResolutionResult(
        mapped_players,
        len(players),
        already_mapped,
        newly_mapped,
        ambiguous,
        not_found,
        profile_rows_updated,
        unmatched,
        failed,
    )


def main() -> int:
    args = parse_args()
    if not settings.espn_historical_stats_enabled and not args.ignore_feature_flag and not args.dry_run:
        print(
            "ESPN historical import is disabled. Run `make env` (or set "
            "ESPN_HISTORICAL_STATS_ENABLED=true in this worktree's .env), then retry. "
            "Use --ignore-feature-flag only for an intentional one-off import."
        )
        return 2

    db = SessionLocal()
    try:
        query = db.query(Player).order_by(Player.sheet_adp.asc().nullslast(), Player.id.asc())
        if args.player_ids:
            query = query.filter(Player.id.in_(args.player_ids))
        players = query.all()
        if args.limit is not None:
            players = players[: max(0, args.limit)]

        resolution = resolve_players_for_import(
            db,
            players,
            resolve_missing=not args.skip_identity_resolution,
            dry_run=args.dry_run,
        )
        mapped_players = resolution.mapped_players

        if args.dry_run:
            print(
                "ESPN historical identity preflight: "
                f"{resolution.scanned} players scanned, "
                f"{resolution.already_mapped} already mapped, "
                f"{resolution.unmatched} requiring safe ESPN lookup, "
                f"{len(mapped_players)} ready to import without lookup."
            )
            return 0

        print(
            "ESPN historical identity resolution: "
            f"{resolution.scanned} players scanned, "
            f"{resolution.already_mapped} already mapped, "
            f"{resolution.newly_mapped} newly mapped, "
            f"{resolution.ambiguous} ambiguous, {resolution.not_found} not found, "
            f"{resolution.profile_rows_updated} profile rows updated, {resolution.failed} failed."
        )

        started_at = datetime.now(timezone.utc)
        run = HistoricalStatImportRun(
            provider="espn",
            requested_player_ids=[player.id for player in players],
            requested_seasons=args.game_log_seasons,
            players_unmatched=len(players)-len(mapped_players),
            players_not_found=resolution.not_found,
            status="running",
            started_at=started_at,
            players_requested=len(players),
            trigger_type="manual",
        )
        db.add(run)
        db.commit()

        errors: dict[str, str] = {str(player.id): "No trusted ESPN identity; production unknown." for player in players if player.id not in {row.id for row in mapped_players}}
        coverage: dict = {}
        for player in mapped_players:
            try:
                response=fetch_and_store_player_history(db, player, allow_disabled=args.ignore_feature_flag)
                coverage[str(player.id)]={"season_stats":response.status,"game_logs":[]}
                if args.game_log_seasons:
                    from collegefootballfantasy_api.app.services.providers.espn_historical.client import ESPNHistoricalStatsClient
                    from collegefootballfantasy_api.app.services.player_game_history import store_player_game_history
                    provider_id=resolve_espn_player_id(db,player)
                    provider=ESPNHistoricalStatsClient()
                    for season in sorted(set(args.game_log_seasons)):
                        payload=provider.get_athlete_game_log(provider_id,season=season)
                        result=store_player_game_history(db,player,provider_player_id=provider_id,season=season,payload=payload)
                        if player.position=='K' and result['games']==0:
                            from collegefootballfantasy_api.app.services.player_game_history import store_boxscore_game_history,game_history_fallback_team_ids,completed_schedule_event_ids
                            summaries=ESPNClient()
                            profile=summaries.get_athlete_profile(provider_id)
                            event_ids=set(payload.get('events',{}))
                            for team_id in game_history_fallback_team_ids(payload,season=season,profile=profile):
                                events=summaries.get_team_schedule_events(team_id,season=season)
                                event_ids.update(completed_schedule_event_ids(events,team_id=team_id))
                            for event_id in sorted(event_ids):
                                boxed=store_boxscore_game_history(db,player,provider_player_id=provider_id,season=season,summary=summaries.get_summary(event_id))
                                result['games']+=boxed['games']
                                for key in ('inserted','updated','unchanged'):result[key]+=boxed[key]
                                time.sleep(1/max(settings.espn_historical_stats_requests_per_second,.1))
                            if result['games']:result['status']='available'
                        coverage[str(player.id)]["game_logs"].append(result)
                if response.status=="available" or any(row["games"] for row in coverage[str(player.id)]["game_logs"]):
                    run.players_succeeded += 1
                else:
                    run.players_not_found += 1
                    errors[str(player.id)]="Provider returned no season or game stats"
                db.commit()
            except Exception as exc:
                db.rollback()
                run = db.get(HistoricalStatImportRun, run.id)
                run.players_failed += 1
                errors[str(player.id)] = str(exc)
                db.commit()

        run = db.get(HistoricalStatImportRun, run.id)
        run.completed_at = datetime.now(timezone.utc)
        run.status = "completed_with_errors" if errors else "completed"
        run.error_summary = {"errors":errors,"coverage":coverage}
        db.commit()
        print(
            "ESPN historical statistics import: "
            f"{run.players_succeeded} stats succeeded, {run.players_failed} stats failed, "
            f"{run.players_requested} mapped players processed ({run.status})."
        )
        return 1 if errors else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
