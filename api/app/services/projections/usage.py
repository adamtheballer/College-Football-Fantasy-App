from __future__ import annotations

from collections import defaultdict
from typing import Any

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.usage_share import UsageShare
from collegefootballfantasy_api.app.services.projections.constants import (
    DEFAULT_RB_CARRY_SHARES,
    DEFAULT_RB_TARGET_SHARE,
    DEFAULT_TE_TARGET_SHARE,
    DEFAULT_WR_TARGET_SHARES,
)


def _stat_value(stats: dict[str, Any], keys: list[str]) -> float:
    for key in keys:
        if key in stats and stats[key] is not None:
            try:
                return float(stats[key])
            except (TypeError, ValueError):
                continue
    return 0.0


def compute_usage_shares(
    players: list[Player], player_stats: dict[int, dict[str, Any]], season: int, week: int
) -> list[UsageShare]:
    team_groups: dict[str, list[Player]] = defaultdict(list)
    for player in players:
        team_groups[player.school].append(player)

    shares: list[UsageShare] = []
    for team, roster in team_groups.items():
        # Aggregate team totals from stats (if available)
        team_rush_attempts = 0.0
        team_targets = 0.0
        for player in roster:
            stats = player_stats.get(player.id, {})
            team_rush_attempts += _stat_value(stats, ["RushingAttempts", "RushAttempts"])
            team_targets += _stat_value(stats, ["ReceivingTargets", "Targets"])

        # If no stats yet, fall back to defaults by position
        if team_rush_attempts == 0.0:
            rbs = [p for p in roster if p.position.upper() == "RB"]
            for idx, rb in enumerate(sorted(rbs, key=lambda p: p.name)):
                share = DEFAULT_RB_CARRY_SHARES[min(idx, len(DEFAULT_RB_CARRY_SHARES) - 1)]
                shares.append(
                    UsageShare(
                        player_id=rb.id,
                        season=season,
                        week=week,
                        rush_share=share,
                        target_share=DEFAULT_RB_TARGET_SHARE / max(len(rbs), 1),
                        red_zone_share=share,
                        inside_five_share=share,
                        snap_share=share,
                        route_share=DEFAULT_RB_TARGET_SHARE / max(len(rbs), 1),
                    )
                )
            wrs = [p for p in roster if p.position.upper() == "WR"]
            for idx, wr in enumerate(sorted(wrs, key=lambda p: p.name)):
                share = DEFAULT_WR_TARGET_SHARES[min(idx, len(DEFAULT_WR_TARGET_SHARES) - 1)]
                shares.append(
                    UsageShare(
                        player_id=wr.id,
                        season=season,
                        week=week,
                        rush_share=0.0,
                        target_share=share,
                        red_zone_share=share,
                        inside_five_share=share,
                        snap_share=share,
                        route_share=share,
                    )
                )
            tes = [p for p in roster if p.position.upper() == "TE"]
            for idx, te in enumerate(sorted(tes, key=lambda p: p.name)):
                share = DEFAULT_TE_TARGET_SHARE / max(len(tes), 1)
                shares.append(
                    UsageShare(
                        player_id=te.id,
                        season=season,
                        week=week,
                        rush_share=0.0,
                        target_share=share,
                        red_zone_share=share,
                        inside_five_share=share,
                        snap_share=share,
                        route_share=share,
                    )
                )
            continue

        for player in roster:
            stats = player_stats.get(player.id, {})
            rush_attempts = _stat_value(stats, ["RushingAttempts", "RushAttempts"])
            targets = _stat_value(stats, ["ReceivingTargets", "Targets"])
            rush_share = rush_attempts / max(team_rush_attempts, 1.0)
            target_share = targets / max(team_targets, 1.0)
            shares.append(
                UsageShare(
                    player_id=player.id,
                    season=season,
                    week=week,
                    rush_share=rush_share,
                    target_share=target_share,
                    red_zone_share=target_share,
                    inside_five_share=target_share,
                    snap_share=target_share,
                    route_share=target_share,
                )
            )

    return shares
