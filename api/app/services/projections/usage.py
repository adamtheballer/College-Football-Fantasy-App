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


# A single final box score is informative, but it is not a complete role
# forecast. Keep most of the established depth-chart prior in the first
# postgame outlook so a one-game target/carry outlier cannot collapse the
# following week's projection. This also protects provider payloads that omit
# targets or carries for an otherwise valid final box score.
SINGLE_GAME_USAGE_OBSERVED_WEIGHT = 0.35


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

        rbs = sorted((player for player in roster if player.position.upper() == "RB"), key=lambda player: player.name)
        wrs = sorted((player for player in roster if player.position.upper() == "WR"), key=lambda player: player.name)
        tes = sorted((player for player in roster if player.position.upper() == "TE"), key=lambda player: player.name)
        fallback_rush_share = {
            player.id: DEFAULT_RB_CARRY_SHARES[min(index, len(DEFAULT_RB_CARRY_SHARES) - 1)]
            for index, player in enumerate(rbs)
        }
        fallback_target_share = {
            **{player.id: DEFAULT_RB_TARGET_SHARE / max(len(rbs), 1) for player in rbs},
            **{
                player.id: DEFAULT_WR_TARGET_SHARES[min(index, len(DEFAULT_WR_TARGET_SHARES) - 1)]
                for index, player in enumerate(wrs)
            },
            **{player.id: DEFAULT_TE_TARGET_SHARE / max(len(tes), 1) for player in tes},
        }

        for player in roster:
            stats = player_stats.get(player.id, {})
            rush_attempts = _stat_value(stats, ["RushingAttempts", "RushAttempts"])
            targets = _stat_value(stats, ["ReceivingTargets", "Targets"])
            default_rush = fallback_rush_share.get(player.id, 0.0)
            default_target = fallback_target_share.get(player.id, 0.0)
            observed_rush = rush_attempts / team_rush_attempts if team_rush_attempts > 0 else default_rush
            observed_target = targets / team_targets if team_targets > 0 else default_target
            rush_share = (
                (1.0 - SINGLE_GAME_USAGE_OBSERVED_WEIGHT) * default_rush
                + SINGLE_GAME_USAGE_OBSERVED_WEIGHT * observed_rush
            )
            target_share = (
                (1.0 - SINGLE_GAME_USAGE_OBSERVED_WEIGHT) * default_target
                + SINGLE_GAME_USAGE_OBSERVED_WEIGHT * observed_target
            )
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
