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


def _estimate_targets(stats: dict[str, Any], position: str) -> float:
    targets = _stat_value(stats, ["ReceivingTargets", "Targets"])
    if targets > 0:
        return targets

    receptions = _stat_value(stats, ["Receptions"])
    if receptions <= 0:
        return 0.0

    pos = position.upper()
    inferred_catch_rate = 0.62
    if pos == "RB":
        inferred_catch_rate = 0.74
    elif pos == "TE":
        inferred_catch_rate = 0.68

    return receptions / inferred_catch_rate


def _role_score(player: Player, stats: dict[str, Any]) -> float:
    pos = player.position.upper()
    if pos == "QB":
        return _stat_value(stats, ["PassingAttempts", "PassAttempts"]) + (
            _stat_value(stats, ["PassingYards", "PassYards"]) / 100.0
        )
    if pos == "RB":
        return _stat_value(stats, ["RushingAttempts", "RushAttempts"]) + (
            _stat_value(stats, ["RushingYards", "RushYards"]) / 50.0
        )
    if pos in {"WR", "TE"}:
        return _estimate_targets(stats, pos) + (_stat_value(stats, ["ReceivingYards", "RecYards"]) / 75.0)
    return 0.0


def _descending_weights(count: int, base: list[float]) -> list[float]:
    if count <= 0:
        return []
    if not base:
        return [1.0 / count for _ in range(count)]
    weights: list[float] = []
    for idx in range(count):
        if idx < len(base):
            weights.append(max(base[idx], 0.0))
        else:
            tail = max(base[-1], 0.01) * (0.6 ** (idx - len(base) + 1))
            weights.append(max(tail, 0.005))
    total = sum(weights) or 1.0
    return [value / total for value in weights]


def _ranked_group(players: list[Player], player_stats: dict[int, dict[str, Any]]) -> list[Player]:
    return sorted(
        players,
        key=lambda player: (_role_score(player, player_stats.get(player.id, {})), player.name),
        reverse=True,
    )


def compute_usage_shares(
    players: list[Player], player_stats: dict[int, dict[str, Any]], season: int, week: int
) -> list[UsageShare]:
    team_groups: dict[str, list[Player]] = defaultdict(list)
    for player in players:
        team_groups[player.school].append(player)

    shares: list[UsageShare] = []
    for team, roster in team_groups.items():
        qbs = [p for p in roster if p.position.upper() == "QB"]
        rbs = [p for p in roster if p.position.upper() == "RB"]
        wrs = [p for p in roster if p.position.upper() == "WR"]
        tes = [p for p in roster if p.position.upper() == "TE"]

        ranked_qbs = _ranked_group(qbs, player_stats)
        ranked_rbs = _ranked_group(rbs, player_stats)
        ranked_wrs = _ranked_group(wrs, player_stats)
        ranked_tes = _ranked_group(tes, player_stats)

        # Aggregate team totals from stats (if available)
        team_rush_attempts = 0.0
        team_targets = 0.0
        team_pass_attempts = 0.0
        for player in roster:
            stats = player_stats.get(player.id, {})
            team_rush_attempts += _stat_value(stats, ["RushingAttempts", "RushAttempts"])
            team_targets += _estimate_targets(stats, player.position)
            team_pass_attempts += _stat_value(stats, ["PassingAttempts", "PassAttempts"])

        # If no stats yet, fall back to defaults by position
        if team_rush_attempts == 0.0 and team_targets == 0.0 and team_pass_attempts == 0.0:
            qb_snap_shares = _descending_weights(len(ranked_qbs), [0.9, 0.1])
            rb_carry_shares = _descending_weights(len(ranked_rbs), DEFAULT_RB_CARRY_SHARES)
            wr_target_weights = _descending_weights(len(ranked_wrs), DEFAULT_WR_TARGET_SHARES)
            te_target_weights = _descending_weights(len(ranked_tes), [1.0 for _ in ranked_tes])

            wr_pool = max(0.0, 1.0 - DEFAULT_RB_TARGET_SHARE - DEFAULT_TE_TARGET_SHARE)
            wr_target_shares = [weight * wr_pool for weight in wr_target_weights]
            rb_target_shares = [weight * DEFAULT_RB_TARGET_SHARE for weight in rb_carry_shares]
            te_target_shares = [weight * DEFAULT_TE_TARGET_SHARE for weight in te_target_weights]

            for idx, qb in enumerate(ranked_qbs):
                snap_share = qb_snap_shares[min(idx, len(qb_snap_shares) - 1)] if qbs else 0.0
                rush_share = 0.14 * snap_share
                shares.append(
                    UsageShare(
                        player_id=qb.id,
                        season=season,
                        week=week,
                        rush_share=rush_share,
                        target_share=0.0,
                        red_zone_share=snap_share,
                        inside_five_share=snap_share,
                        snap_share=snap_share,
                        route_share=snap_share,
                    )
                )
            for idx, rb in enumerate(ranked_rbs):
                share = rb_carry_shares[min(idx, len(rb_carry_shares) - 1)] if rb_carry_shares else 0.0
                target_share = rb_target_shares[min(idx, len(rb_target_shares) - 1)] if rb_target_shares else 0.0
                shares.append(
                    UsageShare(
                        player_id=rb.id,
                        season=season,
                        week=week,
                        rush_share=share,
                        target_share=target_share,
                        red_zone_share=share,
                        inside_five_share=share,
                        snap_share=share,
                        route_share=target_share,
                    )
                )
            for idx, wr in enumerate(ranked_wrs):
                share = wr_target_shares[min(idx, len(wr_target_shares) - 1)] if wr_target_shares else 0.0
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
            for idx, te in enumerate(ranked_tes):
                share = te_target_shares[min(idx, len(te_target_shares) - 1)] if te_target_shares else 0.0
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

        qb_snap_shares = _descending_weights(len(ranked_qbs), [0.9, 0.1])
        rb_carry_shares = _descending_weights(len(ranked_rbs), DEFAULT_RB_CARRY_SHARES)
        wr_target_weights = _descending_weights(len(ranked_wrs), DEFAULT_WR_TARGET_SHARES)
        te_target_weights = _descending_weights(len(ranked_tes), [1.0 for _ in ranked_tes])
        wr_pool = max(0.0, 1.0 - DEFAULT_RB_TARGET_SHARE - DEFAULT_TE_TARGET_SHARE)

        fallback_target_by_player: dict[int, float] = {}
        for idx, wr in enumerate(ranked_wrs):
            fallback_target_by_player[wr.id] = wr_target_weights[min(idx, len(wr_target_weights) - 1)] * wr_pool
        for idx, rb in enumerate(ranked_rbs):
            fallback_target_by_player[rb.id] = rb_carry_shares[min(idx, len(rb_carry_shares) - 1)] * DEFAULT_RB_TARGET_SHARE
        for idx, te in enumerate(ranked_tes):
            fallback_target_by_player[te.id] = te_target_weights[min(idx, len(te_target_weights) - 1)] * DEFAULT_TE_TARGET_SHARE

        fallback_rush_by_player: dict[int, float] = {}
        for idx, rb in enumerate(ranked_rbs):
            fallback_rush_by_player[rb.id] = rb_carry_shares[min(idx, len(rb_carry_shares) - 1)] if rb_carry_shares else 0.0
        for idx, qb in enumerate(ranked_qbs):
            snap_share = qb_snap_shares[min(idx, len(qb_snap_shares) - 1)] if qb_snap_shares else 0.0
            fallback_rush_by_player[qb.id] = 0.14 * snap_share

        for player in roster:
            stats = player_stats.get(player.id, {})
            rush_attempts = _stat_value(stats, ["RushingAttempts", "RushAttempts"])
            targets = _estimate_targets(stats, player.position)

            if team_rush_attempts > 0:
                rush_share = rush_attempts / max(team_rush_attempts, 1.0)
            else:
                rush_share = fallback_rush_by_player.get(player.id, 0.0)

            if team_targets > 0:
                target_share = targets / max(team_targets, 1.0)
            else:
                target_share = fallback_target_by_player.get(player.id, 0.0)

            snap_share = max(target_share, rush_share)
            if player.position.upper() == "QB":
                pass_attempts = _stat_value(stats, ["PassingAttempts", "PassAttempts"])
                if team_pass_attempts > 0:
                    snap_share = pass_attempts / max(team_pass_attempts, 1.0)
                else:
                    qb_index = ranked_qbs.index(player) if player in ranked_qbs else 0
                    snap_share = qb_snap_shares[min(qb_index, len(qb_snap_shares) - 1)] if qb_snap_shares else 0.0

            shares.append(
                UsageShare(
                    player_id=player.id,
                    season=season,
                    week=week,
                    rush_share=rush_share,
                    target_share=target_share,
                    red_zone_share=snap_share if player.position.upper() == "QB" else target_share,
                    inside_five_share=snap_share if player.position.upper() == "QB" else target_share,
                    snap_share=snap_share,
                    route_share=snap_share,
                )
            )

    return shares
