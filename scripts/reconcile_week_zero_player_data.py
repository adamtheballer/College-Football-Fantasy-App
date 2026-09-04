#!/usr/bin/env python3
"""Audit and idempotently reconcile canonical Week 0 player display rows.

The default is read-only. ``--apply`` only copies already verified final
``PlayerGameStat`` records into their compatibility ``PlayerStat`` row; it
never calls a provider, changes a game identity, or touches fantasy scoring.
"""

from __future__ import annotations

import argparse
import json

from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.provider_identity import PlayerProviderId
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--apply", action="store_true", help="Persist only exact final-stat compatibility upserts after reviewing dry-run output.")
    args = parser.parse_args()
    ensure_models_registered()

    with SessionLocal() as db:
        schedules = db.query(TeamSchedule).filter(
            TeamSchedule.season == args.season,
            TeamSchedule.week == 0,
            TeamSchedule.is_bye.is_(False),
        ).all()
        game_ids = {row.game_id for row in schedules if row.game_id is not None}
        games = {game.id: game for game in db.query(Game).filter(Game.id.in_(game_ids or {-1})).all()}
        final_stats = db.query(PlayerGameStat).filter(
            PlayerGameStat.season == args.season,
            PlayerGameStat.week == 0,
            PlayerGameStat.game_id.in_(game_ids or {-1}),
            PlayerGameStat.source == "espn_final_boxscore",
        ).all()
        player_ids = {row.player_id for row in final_stats}
        players = {player.id: player for player in db.query(Player).filter(Player.id.in_(player_ids or {-1})).all()}
        verified_espn_ids = {
            row.player_id
            for row in db.query(PlayerProviderId).filter(
                PlayerProviderId.provider == "espn",
                PlayerProviderId.verification_status == "verified",
                PlayerProviderId.player_id.in_(player_ids or {-1}),
            ).all()
        }
        existing = {
            row.player_id: row
            for row in db.query(PlayerStat).filter(
                PlayerStat.season == args.season,
                PlayerStat.week == 0,
                PlayerStat.player_id.in_(player_ids or {-1}),
            ).all()
        }
        rows = []
        writes = 0
        for final_stat in final_stats:
            game = games.get(final_stat.game_id)
            current = existing.get(final_stat.player_id)
            action = "UNCHANGED" if current and current.stats == final_stat.stats else "UPSERT_COMPATIBILITY_STAT"
            rows.append({
                "player_id": final_stat.player_id,
                "player": players.get(final_stat.player_id).name if final_stat.player_id in players else None,
                "game_id": final_stat.game_id,
                "event_id": game.external_id if game else None,
                "team": players.get(final_stat.player_id).school if final_stat.player_id in players else None,
                "verified_espn_identity": final_stat.player_id in verified_espn_ids,
                "action": action,
            })
            if args.apply and action == "UPSERT_COMPATIBILITY_STAT":
                if current is None:
                    current = PlayerStat(
                        player_id=final_stat.player_id,
                        season=args.season,
                        week=0,
                        source="espn_final_boxscore",
                        verified=True,
                        stats=final_stat.stats,
                    )
                    db.add(current)
                else:
                    current.source = "espn_final_boxscore"
                    current.verified = True
                    current.stats = final_stat.stats
                writes += 1
        report = {
            "season": args.season,
            "dry_run": not args.apply,
            "week_zero_schedule_rows": len(schedules),
            "week_zero_games": len(games),
            "final_player_rows": len(final_stats),
            "writes": writes,
            "unlinked_schedule_rows": [row.id for row in schedules if row.game_id is None],
            "unverified_player_ids": sorted(player_ids - verified_espn_ids),
            "rows": rows,
        }
        if args.apply:
            db.commit()
        else:
            db.rollback()
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
