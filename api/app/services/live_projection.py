"""Deterministic, snapshot-keyed in-game player projections.

No provider client is imported here.  The worker supplies already accepted,
cached data; matchup reads only persisted rows produced by this module.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.stat_normalization import normalize_player_stats
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.live_player_projection import LivePlayerProjection
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.provider_game_poll import ProviderGameSnapshot
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection

LIVE_PROJECTION_V1 = "live_projection_v1"
LIVE_WEIGHT_START = 0.10
LIVE_WEIGHT_MAX = 0.85
USAGE_MIN, USAGE_MAX = 0.60, 1.50
EFFICIENCY_MIN, EFFICIENCY_MAX = 0.75, 1.25
REGULATION_SECONDS = 60 * 60

STAT_FIELDS = (
    "pass_yards", "pass_tds", "interceptions", "rush_yards", "rush_tds",
    "receptions", "rec_yards", "rec_tds", "two_point_conversions", "fumbles_lost",
    "fumble_return_tds", "fg_made_0_30", "fg_made_31_40", "fg_made_41_50",
    "fg_made_51_60", "fg_made_61_plus", "xp_made", "fg_missed",
)


def _number(value: Any) -> float:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def regulation_game_progress(period: int | None, game_clock: str | None) -> float | None:
    """Return regulation clock progress only when ESPN supplied both inputs."""
    if period is None or not 1 <= int(period) <= 4 or not isinstance(game_clock, str):
        return None
    parts = game_clock.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        minutes, seconds = (int(value) for value in parts)
    except ValueError:
        return None
    if not 0 <= minutes <= 15 or not 0 <= seconds < 60:
        return None
    elapsed = (int(period) - 1) * 900 + (900 - (minutes * 60 + seconds))
    return _clamp(elapsed / REGULATION_SECONDS, 0.0, 1.0)


def weekly_projection_stats(row: WeeklyProjection) -> dict[str, float]:
    return {field: _number(getattr(row, field, 0.0)) for field in STAT_FIELDS}


def _usage_baseline(position: str | None, pregame: Mapping[str, float]) -> tuple[str | None, float]:
    normalized = (position or "").upper()
    if normalized in {"WR", "TE"}:
        return "targets", _number(pregame.get("targets"))
    if normalized == "RB":
        return "rush_attempts", _number(pregame.get("rush_attempts"))
    if normalized == "QB":
        return "pass_attempts", _number(pregame.get("pass_attempts"))
    return None, 0.0


def _live_usage(raw: Mapping[str, Any], position: str | None, expected_key: str | None) -> tuple[float | None, str | None]:
    # Only consume explicit provider fields.  Receptions are an intentionally
    # labelled lower-fidelity fallback for pass-catcher targets.
    aliases = {
        "targets": ("targets", "Targets"),
        "rush_attempts": ("rush_attempts", "rushingAttempts", "RushingAttempts"),
        "pass_attempts": ("pass_attempts", "passingAttempts", "PassingAttempts"),
    }
    if expected_key:
        for field in aliases.get(expected_key, ()):
            if field in raw:
                return _number(raw[field]), expected_key
    if (position or "").upper() in {"WR", "TE", "RB"} and any(key in raw for key in ("receptions", "Receptions")):
        return _number(raw.get("receptions", raw.get("Receptions"))), "receptions_fallback"
    return None, None


def _efficiency_multiplier(position: str | None, pregame: Mapping[str, float], current: Mapping[str, float]) -> tuple[float, str | None]:
    normalized = (position or "").upper()
    if normalized in {"WR", "TE", "RB"} and pregame.get("receptions", 0) >= 1 and current.get("receptions", 0) >= 2:
        expected = pregame["rec_yards"] / max(pregame["receptions"], 1)
        observed = current.get("rec_yards", 0) / max(current.get("receptions", 0), 1)
        return _clamp(1 + 0.25 * ((observed / max(expected, 1)) - 1), EFFICIENCY_MIN, EFFICIENCY_MAX), "yards_per_reception"
    return 1.0, None


@dataclass(frozen=True)
class LiveProjectionResult:
    projected_final_stats: dict[str, float]
    projected_remaining_stats: dict[str, float]
    game_progress: float | None
    projection_status: str
    confidence: float
    fallback_reason: str | None
    projected_remaining_fantasy_points: float | None
    observability: dict[str, Any]


def project_live_player(
    *,
    pregame_stats: Mapping[str, float],
    live_stats: Mapping[str, Any],
    position: str | None,
    game_status: str,
    game_progress: float | None,
    previous_projection: Mapping[str, float] | None = None,
    ruled_out: bool = False,
    pregame_fantasy_points: float | None = None,
) -> LiveProjectionResult:
    """Project a final stat line from a pregame prior and one cached snapshot.

    Touchdowns/interceptions are never pace-extrapolated: only the pregame
    remaining expectation is scaled.  Missing reliable clock keeps the prior
    projection intact and records the fallback instead of guessing time.
    """
    prior = {field: _number(pregame_stats.get(field)) for field in STAT_FIELDS}
    current = normalize_player_stats(live_stats, position)
    current = {field: _number(current.get(field)) for field in STAT_FIELDS}
    status = (game_status or "").lower()
    if status in {"final", "post"} or ruled_out:
        reason = "final" if status in {"final", "post"} else "authoritative_out"
        return LiveProjectionResult(current, {field: 0.0 for field in STAT_FIELDS}, 1.0 if status in {"final", "post"} else game_progress, "FINAL" if status in {"final", "post"} else "OUT", 1.0, reason, 0.0, {"live_weight": 1.0, "usage_multiplier": 1.0, "efficiency_multiplier": 1.0})
    if status != "live":
        return LiveProjectionResult(prior, prior, game_progress, "PRE", 0.0, "game_not_live", pregame_fantasy_points, {"live_weight": 0.0, "usage_multiplier": 1.0, "efficiency_multiplier": 1.0})
    if game_progress is None:
        retained = {field: _number((previous_projection or prior).get(field, prior[field])) for field in STAT_FIELDS}
        return LiveProjectionResult(retained, {field: max(0.0, retained[field] - current[field]) for field in STAT_FIELDS}, None, "STALE", 0.0, "missing_game_progress", None, {"live_weight": 0.0, "usage_multiplier": 1.0, "efficiency_multiplier": 1.0})

    progress = _clamp(game_progress, 0.0, 1.0)
    if not any(abs(value) > 0 for value in prior.values()) and _number(pregame_fantasy_points) > 0:
        remaining_points = _number(pregame_fantasy_points) * (1 - progress)
        return LiveProjectionResult(current, {field: 0.0 for field in STAT_FIELDS}, progress, "LIVE", round(progress, 3), "fantasy_points_only", remaining_points, {"live_weight": 0.0, "usage_multiplier": 1.0, "efficiency_multiplier": 1.0, "raw_remaining_fraction": 1 - progress})
    # Clamp the normalized base before the fractional power. At kickoff it is
    # negative before clamping, and a negative value to ``** 1.5`` becomes a
    # complex number instead of the intended zero live-evidence weight.
    normalized_live_progress = _clamp((progress - LIVE_WEIGHT_START) / (1 - LIVE_WEIGHT_START), 0.0, 1.0)
    live_weight = _clamp(normalized_live_progress ** 1.5, 0.0, LIVE_WEIGHT_MAX)
    expected_key, expected_usage = _usage_baseline(position, pregame_stats)
    observed_usage, usage_source = _live_usage(live_stats, position, expected_key)
    if expected_usage > 0 and observed_usage is not None:
        expected_so_far = max(expected_usage * progress, 0.25)
        usage_ratio = observed_usage / expected_so_far
        usage_multiplier = _clamp(1 + live_weight * (usage_ratio - 1), USAGE_MIN, USAGE_MAX)
    else:
        usage_ratio, usage_multiplier = None, 1.0
    efficiency_multiplier, efficiency_source = _efficiency_multiplier(position, pregame_stats, current)
    remaining_fraction = 1 - progress
    remaining: dict[str, float] = {}
    for field in STAT_FIELDS:
        multiplier = usage_multiplier if field in {"pass_yards", "rush_yards", "rec_yards", "receptions"} else 1.0
        if field in {"pass_yards", "rush_yards", "rec_yards"}:
            multiplier *= efficiency_multiplier
        # TDs, INTs, conversions and kick makes retain strongly regressed
        # pregame rates; actual events already live in current stats.
        remaining[field] = max(0.0, prior[field] * remaining_fraction * multiplier)
    raw_final = {field: current[field] + remaining[field] for field in STAT_FIELDS}
    alpha = _clamp(0.35 + 0.50 * progress, 0.35, 0.85)
    if previous_projection:
        final = {field: max(current[field], alpha * raw_final[field] + (1 - alpha) * _number(previous_projection.get(field))) for field in STAT_FIELDS}
    else:
        final = raw_final
    return LiveProjectionResult(
        final,
        {field: max(0.0, final[field] - current[field]) for field in STAT_FIELDS},
        progress,
        "LIVE",
        round(_clamp(0.25 + progress * 0.6, 0.0, 0.9), 3),
        "usage_unavailable" if observed_usage is None else None,
        None,
        {"live_weight": round(live_weight, 4), "usage_source": usage_source, "expected_usage": expected_usage or None, "observed_usage": observed_usage, "usage_ratio": usage_ratio, "usage_multiplier": round(usage_multiplier, 4), "efficiency_source": efficiency_source, "efficiency_multiplier": round(efficiency_multiplier, 4), "raw_remaining_fraction": remaining_fraction, "smoothing_alpha": alpha},
    )


def _hash_input(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def persist_live_projections_for_snapshot(db: Session, *, snapshot: ProviderGameSnapshot) -> int:
    """Persist once per accepted snapshot.  This function performs no I/O."""
    game = db.query(Game).filter(Game.external_id == snapshot.provider_game_id).first()
    if game is None or snapshot.event_state not in {"live", "final"}:
        return 0
    rows = snapshot.normalized_rows if isinstance(snapshot.normalized_rows, list) else []
    player_ids = {int(row.get("player_id")) for row in rows if isinstance(row, dict) and row.get("player_id") is not None}
    if not player_ids:
        return 0
    projections = {
        row.player_id: row for row in db.query(WeeklyProjection).filter(
            WeeklyProjection.season == snapshot.season, WeeklyProjection.week == snapshot.week,
            WeeklyProjection.player_id.in_(player_ids), WeeklyProjection.is_published.is_(True),
        ).all()
    }
    players = {row.id: row for row in db.query(Player).filter(Player.id.in_(player_ids)).all()}
    previous_rows = db.query(LivePlayerProjection).filter(
        LivePlayerProjection.player_id.in_(player_ids), LivePlayerProjection.game_id == game.id,
    ).order_by(LivePlayerProjection.calculated_at.desc(), LivePlayerProjection.id.desc()).all()
    previous: dict[int, LivePlayerProjection] = {}
    for row in previous_rows:
        previous.setdefault(row.player_id, row)
    persisted = 0
    snapshot_at = snapshot.provider_updated_at or snapshot.captured_at or datetime.now(timezone.utc)
    progress = regulation_game_progress(snapshot.event_period, snapshot.event_clock)
    for normalized in rows:
        if not isinstance(normalized, dict) or normalized.get("player_id") is None:
            continue
        player_id = int(normalized["player_id"])
        pregame = projections.get(player_id)
        player = players.get(player_id)
        if pregame is None or player is None:
            continue
        raw_stats = normalized.get("stats") if isinstance(normalized.get("stats"), dict) else {}
        prior = weekly_projection_stats(pregame)
        input_hash = _hash_input({"snapshot": snapshot.snapshot_hash, "projection": pregame.id, "prior": prior, "stats": raw_stats, "progress": progress, "status": snapshot.event_state})
        existing = db.query(LivePlayerProjection).filter_by(player_id=player_id, game_id=game.id, provider_snapshot_hash=snapshot.snapshot_hash).one_or_none()
        if existing is not None:
            continue
        earlier = previous.get(player_id)
        result = project_live_player(
            pregame_stats={**prior, "targets": _number(pregame.targets), "pass_attempts": _number(pregame.pass_attempts), "rush_attempts": _number(pregame.rush_attempts)},
            live_stats=raw_stats,
            position=player.position,
            game_status=snapshot.event_state,
            game_progress=progress,
            previous_projection=earlier.projected_final_stats_json if earlier and earlier.provider_snapshot_hash != snapshot.snapshot_hash else None,
            pregame_fantasy_points=_number(pregame.fantasy_points),
        )
        db.add(LivePlayerProjection(
            player_id=player_id, game_id=game.id, pregame_projection_id=pregame.id,
            season=snapshot.season, week=snapshot.week, provider=snapshot.provider,
            provider_snapshot_hash=snapshot.snapshot_hash, provider_snapshot_at=snapshot_at,
            model_version=LIVE_PROJECTION_V1, projection_status=result.projection_status,
            game_period=snapshot.event_period, game_clock=snapshot.event_clock,
            game_progress=result.game_progress, current_stats_json=normalize_player_stats(raw_stats, player.position),
            projected_final_stats_json=result.projected_final_stats, projected_remaining_stats_json=result.projected_remaining_stats,
            projected_remaining_fantasy_points=result.projected_remaining_fantasy_points,
            observability_json=result.observability, confidence=result.confidence, fallback_reason=result.fallback_reason,
            input_hash=input_hash, calculated_at=datetime.now(timezone.utc),
        ))
        persisted += 1
    if persisted:
        db.flush()
    return persisted
