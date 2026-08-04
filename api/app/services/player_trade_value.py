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

VALUE_POLICY_VERSION = "universal_v1"
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
    if player.cfb27_overall is None:
        return None
    return _normalized_trade_value(float(player.cfb27_overall))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    injury = db.query(Injury).filter(Injury.player_id == player_id, Injury.season == season, Injury.week <= week).order_by(Injury.week.desc(), Injury.id.desc()).first()
    status = (injury.status if injury else "ACTIVE").upper()
    scores = {"ACTIVE": (100.0, 1.0), "QUESTIONABLE": (82.0, 0.85), "DOUBTFUL": (55.0, 0.7), "OUT": (30.0, 0.7), "SUSPENDED": (20.0, 0.65), "UNKNOWN": (70.0, 0.55)}
    return scores.get(status, scores["UNKNOWN"])


def _serialize(row: PlayerTradeValue | None, *, preseason_value: float | None = None) -> PlayerTradeValueRead | None:
    if row is None:
        return None
    value = preseason_value if row.week == 0 and preseason_value is not None else _normalized_trade_value(row.value)
    return PlayerTradeValueRead(week=row.week, value=value, tier=value_tier(value), positional_value_rank=row.positional_value_rank, weekly_change=row.weekly_change, confidence=row.confidence, policy_version=row.policy_version, calculated_at=row.calculated_at, factor_breakdown=row.factor_breakdown_json, explanations=row.explanation_json or [])


def get_player_trade_values(db: Session, *, player_id: int, season: int, policy_version: str = VALUE_POLICY_VERSION) -> PlayerTradeValueHistoryRead:
    rows = db.query(PlayerTradeValue).filter(PlayerTradeValue.player_id == player_id, PlayerTradeValue.season == season, PlayerTradeValue.policy_version == policy_version).order_by(PlayerTradeValue.week.asc()).all()
    player = db.get(Player, player_id)
    baseline = preseason_rating_value(player) if player is not None else None
    serialized_rows = [_serialize(row, preseason_value=baseline) for row in rows]
    history = [row for row in serialized_rows if row is not None]
    return PlayerTradeValueHistoryRead(current=history[-1] if history else None, history=history)


def current_trade_value_snapshot(db: Session, *, player_id: int, season: int | None = None) -> dict | None:
    query = db.query(PlayerTradeValue).filter(PlayerTradeValue.player_id == player_id, PlayerTradeValue.policy_version == VALUE_POLICY_VERSION)
    if season is not None:
        query = query.filter(PlayerTradeValue.season == season)
    row = query.order_by(PlayerTradeValue.season.desc(), PlayerTradeValue.week.desc()).first()
    if row is None:
        return None
    player = db.get(Player, player_id)
    baseline = preseason_rating_value(player) if player is not None else None
    value = baseline if row.week == 0 and baseline is not None else _normalized_trade_value(row.value)
    return {"value": value, "tier": value_tier(value), "policy_version": row.policy_version, "week": row.week, "calculated_at": row.calculated_at.isoformat()}


def calculate_player_trade_value(db: Session, *, player_id: int, season: int, week: int, policy_version: str = VALUE_POLICY_VERSION) -> PlayerTradeValue:
    player = db.get(Player, player_id)
    if player is None:
        raise ValueError("player not found")
    rating_weight, performance_weight, future_weight = weekly_value_weights(week)
    pool = _position_pool(db, player.position)
    rating_score = _percentile(player.cfb27_overall, [float(row.cfb27_overall) for row in pool if row.cfb27_overall is not None])
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
    baseline = preseason_rating_value(player)
    if week == 0 and baseline is not None:
        factors = {
            "preseasonRating": baseline,
            "seasonPerformance": 0.0,
            "recentForm": 0.0,
            "futureProjection": 0.0,
            "usageRole": 0.0,
            "availability": 0.0,
            "positionalScarcity": 0.0,
        }
    value = _normalized_trade_value(sum(factors.values()))
    prior = db.query(PlayerTradeValue).filter(PlayerTradeValue.player_id == player.id, PlayerTradeValue.season == season, PlayerTradeValue.policy_version == policy_version, PlayerTradeValue.week < week).order_by(PlayerTradeValue.week.desc()).first()
    explanation = []
    if performance_raw is not None and performance_score >= 70: explanation.append({"direction": "UP", "reason": "SEASON_PERFORMANCE", "label": "Strong current-season production", "impact": round(performance_weight * performance_score / 100, 1)})
    if availability < 90: explanation.append({"direction": "DOWN", "reason": "AVAILABILITY", "label": "Availability concern", "impact": round((100 - availability) * future_weight / 100, 1)})
    if future_score >= 70: explanation.append({"direction": "UP", "reason": "FUTURE_PROJECTION", "label": "Strong rest-of-season outlook", "impact": round(future_weight * future_score / 100, 1)})
    row = db.query(PlayerTradeValue).filter_by(player_id=player.id, season=season, week=week, policy_version=policy_version).one_or_none()
    if row is None:
        row = PlayerTradeValue(player_id=player.id, season=season, week=week, policy_version=policy_version, value=value, tier=value_tier(value), calculated_at=_utcnow(), input_version="weekly-stats-projections-v1")
        db.add(row)
    row.value, row.tier, row.weekly_change = value, value_tier(value), (round(value - prior.value, 1) if prior else None)
    row.confidence = round((1.0 if player.cfb27_overall is not None else 0.45) * availability_confidence, 2)
    row.calculated_at, row.factor_breakdown_json, row.explanation_json = _utcnow(), factors, explanation[:4]
    db.flush()
    return row


def calculate_weekly_trade_values(db: Session, *, season: int, week: int, policy_version: str = VALUE_POLICY_VERSION) -> dict[str, int]:
    rows = [calculate_player_trade_value(db, player_id=player.id, season=season, week=week, policy_version=policy_version) for player in db.query(Player).all()]
    for position in {row_player.position.upper() for row_player in db.query(Player).all()}:
        position_rows = [row for row in rows if db.get(Player, row.player_id).position.upper() == position]
        for rank, row in enumerate(sorted(position_rows, key=lambda item: (-item.value, item.player_id)), start=1): row.positional_value_rank = rank
    db.flush()
    return {"calculated": len(rows), "low_confidence": sum(row.confidence < 0.7 for row in rows)}
