"""Canonical, versioned universal player trade-value policy and publication service."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.schemas.player_trade_value import PlayerTradeValueHistoryRead, PlayerTradeValueRead
from collegefootballfantasy_api.app.services.injury_value import injury_value_multiplier
from collegefootballfantasy_api.app.services.fantasy_week_finality import (
    week_is_authoritatively_finalized,
)

# Preserve the published policy identifier for existing histories. Official
# availability is a controlled adjustment within that preseason policy, not a
# separate source of baseline truth.
PRESEASON_VALUE_POLICY_VERSION = "cfb27_exact_preseason_v1"
IN_SEASON_VALUE_POLICY_VERSION = "universal_v2"
# The default is the policy selected after checking authoritative application
# state; callers must never select a dynamic policy just by passing week=1.
VALUE_POLICY_VERSION = IN_SEASON_VALUE_POLICY_VERSION
MAX_TRADE_VALUE = 99.0
WEIGHT_POLICY: dict[int, tuple[float, float, float]] = {
    0: (1.00, 0.00, 0.00), 1: (0.75, 0.15, 0.10), 2: (0.65, 0.25, 0.10),
    3: (0.55, 0.35, 0.10), 4: (0.45, 0.45, 0.10), 5: (0.375, 0.50, 0.125),
    6: (0.30, 0.55, 0.15), 7: (0.275, 0.60, 0.125), 8: (0.25, 0.625, 0.125),
    9: (0.20, 0.65, 0.15), 10: (1 / 6, 41 / 60, 0.15), 11: (2 / 15, 43 / 60, 0.15),
}
TIER_LABELS = (
    (96, "UNTOUCHABLE"),
    (90, "FRANCHISE_STAR"),
    (85, "EFFECTIVE_STARTER"),
    (80, "GREAT_OPTION"),
    (75, "GOOD_BENCH_OPTION"),
    (70, "GREAT_DEPTH_ROLE"),
    (0, "SPECULATIVE"),
)


def weekly_value_weights(week: int) -> tuple[float, float, float]:
    return WEIGHT_POLICY.get(max(0, min(week, 11)), (0.10, 0.75, 0.15))


def value_tier(value: float) -> str:
    normalized_value = max(0.0, min(float(value), MAX_TRADE_VALUE))
    return next(label for threshold, label in TIER_LABELS if normalized_value >= threshold)


def _normalized_trade_value(value: float) -> float:
    """Keep all value consumers on the user-facing 0–99 scale."""
    return round(max(0.0, min(float(value), MAX_TRADE_VALUE)), 1)


def preseason_rating_value(player: Player) -> float | None:
    """Use the approved CFB 27 rating as the immutable Week 0 baseline."""
    if player.raw_cfb27_rating is None:
        return None
    return float(player.raw_cfb27_rating)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def week_one_is_authoritatively_finalized(db: Session, *, season: int) -> bool:
    """Fail closed until every scheduled app Week 1 matchup is final.

    This is deliberately based on the persisted matchup lifecycle—not the
    wall clock, provider availability, or a scoring-run success flag.  A
    scoring run can be successful while official corrections remain possible.
    """
    return week_is_authoritatively_finalized(db, season=season, week=1)


def active_value_policy_version(db: Session, *, season: int) -> str:
    return IN_SEASON_VALUE_POLICY_VERSION if week_one_is_authoritatively_finalized(db, season=season) else PRESEASON_VALUE_POLICY_VERSION


def _apply_current_value(
    player: Player,
    *,
    value: float | None,
    policy_version: str,
    calculation_week: int,
    inputs: dict,
) -> None:
    player.current_value_rating = _normalized_trade_value(value) if value is not None else None
    player.value_policy_version = policy_version
    player.value_calculation_week = calculation_week
    player.value_calculated_at = _utcnow()
    player.value_input_json = inputs


def _stat_points(stats: dict | None) -> float | None:
    if not stats:
        return None
    for key in ("fantasy_points", "fantasyPoints", "fpts"):
        value = stats.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _percentile(value: float | None, values: list[float], fallback: float = 35.0) -> float:
    if value is None or not values:
        return fallback
    ordered = sorted(values)
    return max(0.0, min(100.0, 100 * sum(item <= value for item in ordered) / len(ordered)))


def _position_pool(db: Session, position: str) -> list[Player]:
    return db.query(Player).filter(func.upper(Player.position) == position.upper()).all()


def _availability_score(db: Session, player_id: int, season: int, week: int) -> tuple[float, float]:
    injury = _latest_injury(db, player_id=player_id, season=season, week=week)
    status = (injury.status if injury else "ACTIVE").upper()
    scores = {"ACTIVE": (100.0, 1.0), "QUESTIONABLE": (82.0, 0.85), "DOUBTFUL": (55.0, 0.7), "OUT": (30.0, 0.7), "SUSPENDED": (20.0, 0.65), "UNKNOWN": (70.0, 0.55)}
    return scores.get(status, scores["UNKNOWN"])


def _latest_injury(db: Session, *, player_id: int, season: int, week: int) -> Injury | None:
    return (
        db.query(Injury)
        .filter(Injury.player_id == player_id, Injury.season == season, Injury.week <= week)
        .order_by(Injury.week.desc(), Injury.id.desc())
        .first()
    )


def _preseason_value_with_availability(db: Session, *, player: Player, season: int) -> tuple[float | None, Injury | None, float]:
    baseline = preseason_rating_value(player)
    injury = _latest_injury(db, player_id=player.id, season=season, week=1)
    multiplier = injury_value_multiplier(
        injury.status if injury else None,
        return_timeline=injury.return_timeline if injury else None,
        is_returning=bool(injury.is_returning) if injury else False,
    )
    return (_normalized_trade_value(baseline * multiplier) if baseline is not None else None), injury, multiplier


def _serialize(row: PlayerTradeValue | None, *, player: Player) -> PlayerTradeValueRead | None:
    if row is None:
        return None
    value = player.current_value_rating
    if value is None:
        return None
    return PlayerTradeValueRead(week=player.value_calculation_week if player.value_calculation_week is not None else row.week, value=value, raw_cfb27_rating=player.raw_cfb27_rating, current_value_rating=value, tier=value_tier(value), positional_value_rank=row.positional_value_rank, weekly_change=row.weekly_change, confidence=row.confidence, policy_version=player.value_policy_version or row.policy_version, calculated_at=player.value_calculated_at or row.calculated_at, factor_breakdown=player.value_input_json or row.factor_breakdown_json, explanations=row.explanation_json or [])


def _current_value_read(player: Player, row: PlayerTradeValue | None = None, *, value: float | None = None, policy_version: str | None = None) -> PlayerTradeValueRead | None:
    value = player.current_value_rating if value is None else value
    if value is None:
        return None
    return PlayerTradeValueRead(
        week=player.value_calculation_week or 0,
        value=float(value),
        raw_cfb27_rating=player.raw_cfb27_rating,
        current_value_rating=float(value),
        tier=value_tier(float(value)),
        positional_value_rank=row.positional_value_rank if row is not None else None,
        weekly_change=row.weekly_change if row is not None else None,
        confidence=row.confidence if row is not None else 1.0,
        policy_version=policy_version or player.value_policy_version or PRESEASON_VALUE_POLICY_VERSION,
        calculated_at=player.value_calculated_at,
        factor_breakdown=player.value_input_json,
        explanations=row.explanation_json if row is not None and row.explanation_json else [],
    )


def get_player_trade_values(db: Session, *, player_id: int, season: int, policy_version: str | None = None) -> PlayerTradeValueHistoryRead:
    player = db.get(Player, player_id)
    if player is None:
        return PlayerTradeValueHistoryRead(current=None, history=[])
    active_policy = active_value_policy_version(db, season=season)
    rows = db.query(PlayerTradeValue).filter(PlayerTradeValue.player_id == player_id, PlayerTradeValue.season == season, PlayerTradeValue.policy_version == active_policy).order_by(PlayerTradeValue.week.asc()).all()
    serialized_rows = [_serialize(row, player=player) for row in rows]
    history = [row for row in serialized_rows if row is not None]
    # Before Week 1 finalizes, the reviewed CFB27 rating is the baseline, with
    # the latest official injury report as the single controlled exception.
    effective_value = (
        _preseason_value_with_availability(db, player=player, season=season)[0]
        if active_policy == PRESEASON_VALUE_POLICY_VERSION
        else player.current_value_rating
    )
    current = (
        _current_value_read(player, rows[-1] if rows else None, value=effective_value, policy_version=active_policy)
        if effective_value is not None
        else None
    )
    return PlayerTradeValueHistoryRead(current=current, history=history)


def current_trade_value_snapshot(db: Session, *, player_id: int, season: int | None = None) -> dict | None:
    player = db.get(Player, player_id)
    if player is None:
        return None
    effective_season = season if season is not None else 2026
    active_policy = active_value_policy_version(db, season=effective_season)
    value = (
        _preseason_value_with_availability(db, player=player, season=effective_season)[0]
        if active_policy == PRESEASON_VALUE_POLICY_VERSION
        else player.current_value_rating
    )
    if value is None:
        return None
    return {"value": float(value), "tier": value_tier(float(value)), "policy_version": active_policy, "week": 0 if active_policy == PRESEASON_VALUE_POLICY_VERSION else player.value_calculation_week or 0, "calculated_at": player.value_calculated_at.isoformat() if player.value_calculated_at else None}


def calculate_player_trade_value(db: Session, *, player_id: int, season: int, week: int, policy_version: str = VALUE_POLICY_VERSION) -> PlayerTradeValue:
    player = db.get(Player, player_id)
    if player is None:
        raise ValueError("player not found")
    baseline = preseason_rating_value(player)
    active_policy = active_value_policy_version(db, season=season)
    if active_policy == PRESEASON_VALUE_POLICY_VERSION:
        if baseline is None:
            raise ValueError("player is missing an approved raw CFB27 rating")
        value, injury, multiplier = _preseason_value_with_availability(db, player=player, season=season)
        assert value is not None
        row = db.query(PlayerTradeValue).filter_by(player_id=player.id, season=season, week=0, policy_version=PRESEASON_VALUE_POLICY_VERSION).one_or_none()
        if row is None:
            row = PlayerTradeValue(player_id=player.id, season=season, week=0, policy_version=PRESEASON_VALUE_POLICY_VERSION, value=value, tier=value_tier(value), calculated_at=_utcnow(), input_version="cfb27-injury-adjusted-preseason-v2")
            db.add(row)
        row.value, row.tier, row.weekly_change, row.confidence = value, value_tier(value), None, 1.0
        row.calculated_at, row.factor_breakdown_json, row.explanation_json = _utcnow(), {"preseasonRating": baseline, "seasonPerformance": 0.0, "recentForm": 0.0, "futureProjection": 0.0, "usageRole": 0.0, "availability": round(multiplier * 100, 2), "positionalScarcity": 0.0}, ([{"direction": "DOWN", "reason": "AVAILABILITY", "label": "Official availability adjustment", "impact": round((1 - multiplier) * 100, 1)}] if multiplier < 1 else [])
        _apply_current_value(player, value=value, policy_version=PRESEASON_VALUE_POLICY_VERSION, calculation_week=0, inputs={"raw_cfb27_rating": player.raw_cfb27_rating, "preseason_guard": "week_1_not_authoritatively_finalized", "availability_multiplier": multiplier, "injury_status": injury.status if injury else "ACTIVE", "return_timeline": injury.return_timeline if injury else None})
        db.flush()
        return row
    rating_weight, performance_weight, future_weight = weekly_value_weights(week)
    pool = _position_pool(db, player.position)
    rating_score = _percentile(player.raw_cfb27_rating, [float(row.raw_cfb27_rating) for row in pool if row.raw_cfb27_rating is not None])
    player_stats = db.query(PlayerStat).filter(PlayerStat.player_id == player.id, PlayerStat.season == season, PlayerStat.week.between(1, max(week, 1)), PlayerStat.verified.is_(True)).order_by(PlayerStat.week.asc()).all()
    points = [value for value in (_stat_points(row.stats) for row in player_stats) if value is not None]
    performance_raw = (sum(points) / len(points)) if points else None
    position_performance: list[float] = []
    for candidate in pool:
        scores = db.query(PlayerStat).filter(PlayerStat.player_id == candidate.id, PlayerStat.season == season, PlayerStat.week.between(1, max(week, 1)), PlayerStat.verified.is_(True)).all()
        values = [value for value in (_stat_points(row.stats) for row in scores) if value is not None]
        if values: position_performance.append(sum(values) / len(values))
    performance_score = _percentile(performance_raw, position_performance, fallback=rating_score)
    projection = db.scalar(
        current_published_projections_query(
            season=season,
            week=max(week, 1),
            player_ids=(player.id,),
        )
    )
    projected = float(projection.fantasy_points) if projection else player.sheet_projected_season_points
    projected_pool = [float(row.sheet_projected_season_points) for row in pool if row.sheet_projected_season_points is not None]
    future_score = _percentile(projected, projected_pool, fallback=rating_score)
    availability, availability_confidence = _availability_score(db, player.id, season, week)
    scarcity = {"QB": 38.0, "RB": 58.0, "WR": 55.0, "TE": 62.0, "K": 25.0}.get(player.position.upper(), 45.0)
    factors = {
        "preseasonRating": round(rating_weight * rating_score, 2),
        "seasonPerformance": round(performance_weight * 0.7 * performance_score, 2),
        "recentForm": round(performance_weight * 0.3 * performance_score, 2),
        "futureProjection": round(future_weight * 0.65 * future_score, 2),
        "usageRole": round(future_weight * 0.2 * future_score, 2),
        "availability": round(future_weight * 0.1 * availability, 2),
        "positionalScarcity": round(future_weight * 0.05 * scarcity, 2),
    }
    value = _normalized_trade_value(sum(factors.values()))
    prior = db.query(PlayerTradeValue).filter(PlayerTradeValue.player_id == player.id, PlayerTradeValue.season == season, PlayerTradeValue.policy_version == active_policy, PlayerTradeValue.week < week).order_by(PlayerTradeValue.week.desc()).first()
    explanation = []
    if performance_raw is not None and performance_score >= 70: explanation.append({"direction": "UP", "reason": "SEASON_PERFORMANCE", "label": "Strong current-season production", "impact": round(performance_weight * performance_score / 100, 1)})
    if availability < 90: explanation.append({"direction": "DOWN", "reason": "AVAILABILITY", "label": "Availability concern", "impact": round((100 - availability) * future_weight / 100, 1)})
    if future_score >= 70: explanation.append({"direction": "UP", "reason": "FUTURE_PROJECTION", "label": "Strong rest-of-season outlook", "impact": round(future_weight * future_score / 100, 1)})
    row = db.query(PlayerTradeValue).filter_by(player_id=player.id, season=season, week=week, policy_version=active_policy).one_or_none()
    if row is None:
        row = PlayerTradeValue(player_id=player.id, season=season, week=week, policy_version=active_policy, value=value, tier=value_tier(value), calculated_at=_utcnow(), input_version="weekly-stats-projections-v2")
        db.add(row)
    row.value, row.tier, row.weekly_change = value, value_tier(value), (round(value - prior.value, 1) if prior else None)
    row.confidence = round((1.0 if player.raw_cfb27_rating is not None else 0.45) * availability_confidence, 2)
    row.calculated_at, row.factor_breakdown_json, row.explanation_json = _utcnow(), factors, explanation[:4]
    _apply_current_value(player, value=value, policy_version=active_policy, calculation_week=week, inputs={"raw_cfb27_rating": player.raw_cfb27_rating, "factors": factors})
    db.flush()
    return row


def calculate_weekly_trade_values(db: Session, *, season: int, week: int, policy_version: str = VALUE_POLICY_VERSION) -> dict[str, int]:
    rows = [calculate_player_trade_value(db, player_id=player.id, season=season, week=week, policy_version=policy_version) for player in db.query(Player).all()]
    for position in {row_player.position.upper() for row_player in db.query(Player).all()}:
        position_rows = [row for row in rows if db.get(Player, row.player_id).position.upper() == position]
        for rank, row in enumerate(sorted(position_rows, key=lambda item: (-item.value, item.player_id)), start=1): row.positional_value_rank = rank
    db.flush()
    return {"calculated": len(rows), "low_confidence": sum(row.confidence < 0.7 for row in rows)}
