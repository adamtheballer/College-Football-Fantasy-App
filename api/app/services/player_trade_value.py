"""Canonical, versioned universal player trade-value policy and publication service."""
from __future__ import annotations

from datetime import datetime, timezone

from collegefootballfantasy_api.app.core.config import settings
from sqlalchemy import func,or_,and_
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
    latest_known_finalized_week, published_finalized_weeks,
)
from collegefootballfantasy_api.app.scoring import get_scoring_rules

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
    return WEIGHT_POLICY.get(max(0, week), (0.10, 0.75, 0.15))


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
    return IN_SEASON_VALUE_POLICY_VERSION if week_one_is_authoritatively_finalized(db, season=season) or 1 in published_finalized_weeks(db,season=season) else PRESEASON_VALUE_POLICY_VERSION


def _apply_current_value(
    player: Player,
    *,
    value: float | None,
    policy_version: str,
    calculation_week: int,
    calculation_season: int,
    inputs: dict,
) -> None:
    if calculation_season != settings.current_season_year:
        return
    inputs = {**inputs, "season": calculation_season}
    existing_season=(player.value_input_json or {}).get("season")
    if existing_season in {None,calculation_season} and player.value_calculation_week is not None and calculation_week < player.value_calculation_week:
        return
    player.current_value_rating = _normalized_trade_value(value) if value is not None else None
    player.value_policy_version = policy_version
    player.value_calculation_week = calculation_week
    player.value_calculated_at = _utcnow()
    player.value_input_json = inputs


def _stat_points(stats: dict | None, *, position: str, rules: dict | None = None) -> float | None:
    from collegefootballfantasy_api.app.services.player_chart_publication import points_from_verified_stats
    return points_from_verified_stats(stats or {}, position=position,rules=rules)


def _value_stat_inputs(db: Session, *, season: int, week: int) -> dict[int,list[dict]]:
    from collegefootballfantasy_api.app.models.player_chart_week import PlayerChartWeek
    finalized = {w for w in range(1,week+1) if week_is_authoritatively_finalized(db,season=season,week=w)}
    from collegefootballfantasy_api.app.services.player_chart_publication import verified_fantasy_week_stats
    facts = {}
    players=db.query(Player).all()
    for finalized_week in sorted(finalized):
        # Share exact game selection and accepted final-game recovery with
        # actual publication; do not sum both opening-slate games.
        for row in verified_fantasy_week_stats(db,season=season,week=finalized_week,players=players).values():
            facts[(row.player_id,finalized_week)] = row.stats
    # Durable facts outrank later live source mutations and survive newly
    # created historical matchups. The publisher applies supported corrections
    # before recalculating the value in this same worker transaction.
    for row in db.query(PlayerChartWeek).filter(PlayerChartWeek.season==season,PlayerChartWeek.week.between(1,week)).all():
        facts[(row.player_id,row.week)] = row.stats_json
    by_player: dict[int,list[dict]] = {}
    for (player_id,_week),stats in sorted(facts.items()):
        by_player.setdefault(player_id,[]).append(stats)
    return by_player


def _percentile(value: float | None, values: list[float], fallback: float = 35.0) -> float:
    if value is None or not values:
        return fallback
    ordered = sorted(values)
    return max(0.0, min(100.0, 100 * sum(item <= value for item in ordered) / len(ordered)))


def _position_pool(db: Session, position: str, *, season: int) -> list[Player]:
    from collegefootballfantasy_api.app.services.player_chart_publication import eligible_chart_players_query
    return eligible_chart_players_query(db,season).filter(func.upper(Player.position)==position.upper()).all()


def _availability_score(db: Session, player_id: int, season: int, week: int) -> tuple[float, float]:
    from collegefootballfantasy_api.app.services.injury_status import normalize_injury_status
    injury = _latest_injury(db, player_id=player_id, season=season, week=week)
    status = normalize_injury_status(injury.status if injury else "ACTIVE")
    status = "ACTIVE" if status=="FULL" else "OUT" if status in {"OUT_FOR_SEASON","INACTIVE","IR"} else status
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
    value = _normalized_trade_value(row.value)
    return PlayerTradeValueRead(week=row.week, value=value, raw_cfb27_rating=(row.input_context_json or {}).get("raw_cfb27_rating"), current_value_rating=value, tier=value_tier(value), positional_value_rank=row.positional_value_rank, weekly_change=row.weekly_change, confidence=row.confidence, policy_version=row.policy_version, calculated_at=row.calculated_at, factor_breakdown=row.factor_breakdown_json, explanations=row.explanation_json or [])


def _current_value_read(player: Player, row: PlayerTradeValue | None = None, *, value: float | None = None, policy_version: str | None = None) -> PlayerTradeValueRead | None:
    value = player.current_value_rating if value is None else value
    if value is None:
        return None
    return PlayerTradeValueRead(
        week=0 if policy_version==PRESEASON_VALUE_POLICY_VERSION else player.value_calculation_week or 0,
        value=_normalized_trade_value(value),
        raw_cfb27_rating=player.raw_cfb27_rating,
        current_value_rating=_normalized_trade_value(value),
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
    rows = db.query(PlayerTradeValue).filter(PlayerTradeValue.player_id == player_id, PlayerTradeValue.season == season, or_(and_(PlayerTradeValue.week==0,PlayerTradeValue.policy_version==PRESEASON_VALUE_POLICY_VERSION),and_(PlayerTradeValue.week.between(1,13),PlayerTradeValue.policy_version==IN_SEASON_VALUE_POLICY_VERSION))).order_by(PlayerTradeValue.week.asc()).all()
    serialized_rows = [_serialize(row, player=player) for row in rows if value_snapshot_is_finalized(db,row)]
    history = [row for row in serialized_rows if row is not None]
    if season != settings.current_season_year:
        return PlayerTradeValueHistoryRead(current=history[-1] if history else None,history=history)
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


def value_snapshot_is_finalized(db: Session, row: PlayerTradeValue) -> bool:
    context = row.input_context_json or {}
    return row.week == 0 or week_is_authoritatively_finalized(db,season=row.season,week=row.week) or (
        context.get("publication_state") == "weekly_finalized"
        and context.get("season") == row.season and context.get("week_cutoff") == row.week
    )


def value_cutoff_context(row: PlayerTradeValue | None) -> dict | None:
    context = row.input_context_json if row else None
    required = {"peer_player_ids","rating_score","future_score","availability","availability_confidence","scarcity","weights","position","season","week_cutoff"}
    return context if context and required.issubset(context) and context["season"]==row.season and context["week_cutoff"]==row.week else None


def current_trade_value_snapshot(db: Session, *, player_id: int, season: int | None = None) -> dict | None:
    player = db.get(Player, player_id)
    if player is None:
        return None
    effective_season = season if season is not None else settings.current_season_year
    active_policy = active_value_policy_version(db, season=effective_season)
    value = (
        _preseason_value_with_availability(db, player=player, season=effective_season)[0]
        if active_policy == PRESEASON_VALUE_POLICY_VERSION
        else player.current_value_rating
    )
    if value is None:
        return None
    return {"value": _normalized_trade_value(value), "tier": value_tier(float(value)), "policy_version": active_policy, "week": 0 if active_policy == PRESEASON_VALUE_POLICY_VERSION else player.value_calculation_week or 0, "calculated_at": player.value_calculated_at.isoformat() if player.value_calculated_at else None}


def calculate_player_trade_value(db: Session, *, player_id: int, season: int, week: int, policy_version: str = VALUE_POLICY_VERSION, _batch: dict | None = None) -> PlayerTradeValue:
    db.flush()
    player = db.query(Player).filter(Player.id == player_id).with_for_update().populate_existing().one_or_none()
    if player is None:
        raise ValueError("player not found")
    baseline = preseason_rating_value(player)
    active_policy = _batch["active_policy"] if _batch else active_value_policy_version(db, season=season)
    if active_policy == PRESEASON_VALUE_POLICY_VERSION:
        if season!=settings.current_season_year:
            historical=db.query(PlayerTradeValue).filter_by(player_id=player.id,season=season,week=0,policy_version=PRESEASON_VALUE_POLICY_VERSION).one_or_none()
            if historical is None:
                raise ValueError("historical preseason inputs unavailable; refusing current-season baseline backfill")
            return historical
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
        _apply_current_value(player, value=value, policy_version=PRESEASON_VALUE_POLICY_VERSION, calculation_week=0, calculation_season=season, inputs={"raw_cfb27_rating": player.raw_cfb27_rating, "preseason_guard": "week_1_not_authoritatively_finalized", "availability_multiplier": multiplier, "injury_status": injury.status if injury else "ACTIVE", "return_timeline": injury.return_timeline if injury else None})
        db.flush()
        return row
    if not 1 <= week <= 13 or not (_batch["finalized"] if _batch else week_is_authoritatively_finalized(db, season=season, week=week)):
        raise ValueError("value publication requires authoritative finality for its own week")
    existing = db.query(PlayerTradeValue).filter_by(player_id=player.id, season=season, week=week, policy_version=active_policy).with_for_update().one_or_none()
    cutoff_context = value_cutoff_context(existing)
    if season!=settings.current_season_year and cutoff_context is None:
        raise ValueError("historical value inputs unavailable; refusing current-season catalog backfill")
    latest_finalized = _batch["latest_finalized"] if _batch else latest_known_finalized_week(db, season=season)
    if week < latest_finalized and not cutoff_context:
        raise ValueError("historical value inputs unavailable; refusing future-informed backfill")
    rating_weight, performance_weight, future_weight = weekly_value_weights(week)
    historical_position = cutoff_context.get("position", player.position) if cutoff_context else player.position
    pool = _batch["position_pools"].get(historical_position.upper(), []) if _batch else _position_pool(db, historical_position,season=season)
    if cutoff_context:
        peer_ids = set(cutoff_context["peer_player_ids"])
        pool = [candidate for candidate in (_batch["players_by_id"].values() if _batch else db.query(Player).filter(Player.id.in_(peer_ids)).all()) if candidate.id in peer_ids]
        if len(pool)!=len(peer_ids):
            raise ValueError("historical value peers unavailable; preserving the existing snapshot")
    rating_score = _percentile(player.raw_cfb27_rating, [float(row.raw_cfb27_rating) for row in pool if row.raw_cfb27_rating is not None])
    stat_inputs = _batch["stats_by_player"] if _batch else _value_stat_inputs(db,season=season,week=week)
    scoring_rules = (cutoff_context or {}).get("scoring_rules",get_scoring_rules())
    points = [value for value in (_stat_points(stats, position=historical_position,rules=scoring_rules) for stats in stat_inputs.get(player.id,[])) if value is not None]
    performance_raw = (sum(points) / len(points)) if points else None
    position_performance: list[float] = []
    for candidate in pool:
        values = [value for value in (_stat_points(stats, position=(cutoff_context or {}).get("peer_positions", {}).get(str(candidate.id), candidate.position),rules=scoring_rules) for stats in stat_inputs.get(candidate.id,[])) if value is not None]
        if values: position_performance.append(sum(values) / len(values))
    performance_score = _percentile(performance_raw, position_performance, fallback=rating_score)
    projection = _batch["projections"].get(player.id) if _batch else db.scalar(
        current_published_projections_query(
            season=season,
            week=max(week, 1),
            player_ids=(player.id,),
        )
    )
    projected = float(projection.fantasy_points) if projection else player.sheet_projected_season_points
    if projection:
        peer_projections = [_batch["projections"][candidate.id] for candidate in pool if candidate.id in _batch["projections"]] if _batch else db.scalars(current_published_projections_query(season=season, week=week, player_ids=tuple(candidate.id for candidate in pool))).all()
        projected_pool = [float(candidate.fantasy_points) for candidate in peer_projections if candidate.fantasy_points is not None]
    else:
        projected_pool = [float(row.sheet_projected_season_points) for row in pool if row.sheet_projected_season_points is not None]
    future_score = _percentile(projected, projected_pool, fallback=rating_score)
    availability, availability_confidence = _availability_score(db, player.id, season, week)
    scarcity = {"QB": 38.0, "RB": 58.0, "WR": 55.0, "TE": 62.0, "K": 25.0}.get(player.position.upper(), 45.0)
    if cutoff_context:
        rating_score = cutoff_context["rating_score"]
        future_score = cutoff_context["future_score"]
        availability = cutoff_context["availability"]
        availability_confidence = cutoff_context["availability_confidence"]
        scarcity = cutoff_context["scarcity"]
        rating_weight, performance_weight, future_weight = cutoff_context["weights"]
        if performance_raw is None:
            performance_score = rating_score
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
    confidence_rating = (cutoff_context or {}).get("raw_cfb27_rating",player.raw_cfb27_rating)
    row.confidence = round((1.0 if confidence_rating is not None else 0.45) * availability_confidence, 2)
    row.calculated_at, row.factor_breakdown_json, row.explanation_json = _utcnow(), factors, explanation[:4]
    row.input_context_json = cutoff_context or {"raw_cfb27_rating": player.raw_cfb27_rating, "position": player.position, "peer_positions": {str(candidate.id): candidate.position for candidate in pool}, "peer_player_ids": [candidate.id for candidate in pool], "rating_score": rating_score, "future_score": future_score, "availability": availability, "availability_confidence": availability_confidence, "scarcity": scarcity, "weights": [rating_weight, performance_weight, future_weight], "season": season, "week_cutoff": week, "captured_at": row.calculated_at.isoformat(), "scoring_context": "standard_cffb", "projection_id": projection.id if projection else None}
    row.input_context_json = {**row.input_context_json, "publication_state": "weekly_finalized", "scoring_rules": scoring_rules,"peer_scope":cutoff_context.get("peer_scope","retained_original_cohort") if cutoff_context else "approved_game_catalog_at_capture"}
    row.input_version = "weekly-stats-projections-v4-cutoff-eligible"
    _apply_current_value(player, value=value, policy_version=active_policy, calculation_week=week, calculation_season=season, inputs={"raw_cfb27_rating": player.raw_cfb27_rating, "factors": factors})
    db.flush()
    return row


def calculate_weekly_trade_values(db: Session, *, season: int, week: int, policy_version: str = VALUE_POLICY_VERSION) -> dict[str, int]:
    from collegefootballfantasy_api.app.models.player_chart_week import PlayerChartPublicationRun
    from collegefootballfantasy_api.app.services.player_chart_publication import eligible_chart_players_query, chart_input_fingerprint, previous_chart_run, chart_output_fingerprint
    active_policy = active_value_policy_version(db, season=season)
    if active_policy != PRESEASON_VALUE_POLICY_VERSION and not week_is_authoritatively_finalized(db, season=season, week=week):
        raise ValueError("value publication requires authoritative finality")
    fingerprint = chart_input_fingerprint(db, season=season, week=week, metric="value")
    previous_run = previous_chart_run(db, season=season, week=week, metric="value", fingerprint=fingerprint)
    if previous_run:
        return {**previous_run.coverage_json, "status": previous_run.status, "run_id": previous_run.id, "unchanged": previous_run.coverage_json["calculated"]}
    run = PlayerChartPublicationRun(season=season, week=week, status="running", started_at=_utcnow(), coverage_json={})
    db.add(run); db.flush()
    position_pools = {}
    all_players = db.query(Player).all()
    for candidate in eligible_chart_players_query(db,season).all():
        position_pools.setdefault(candidate.position.upper(), []).append(candidate)
    batch_context = {"active_policy": active_policy, "finalized": week_is_authoritatively_finalized(db, season=season, week=week), "latest_finalized": latest_known_finalized_week(db, season=season), "position_pools": position_pools, "players_by_id": {p.id:p for p in all_players}, "stats_by_player": _value_stat_inputs(db,season=season,week=max(week,1)), "projections": {row.player_id: row for row in db.scalars(current_published_projections_query(season=season, week=max(week, 1))).all()}}
    target_week=0 if active_policy==PRESEASON_VALUE_POLICY_VERSION else week
    prior_values={r.player_id:r.value for r in db.query(PlayerTradeValue).filter_by(season=season,week=target_week,policy_version=active_policy).all()}
    rows, failures, missing, changes = [], [], [], []
    recomputed_unchanged=0
    eligible_count, last_id = 0, 0
    while True:
        players = eligible_chart_players_query(db, season).filter(Player.id > last_id).order_by(Player.id).limit(200).all()
        if not players:
            break
        last_id = players[-1].id
        for player in players:
            eligible_count += 1
            if season==settings.current_season_year and active_policy == PRESEASON_VALUE_POLICY_VERSION and preseason_rating_value(player) is None:
                missing.append(player.id)
                continue
            try:
                with db.begin_nested():
                    row = calculate_player_trade_value(db, player_id=player.id, season=season, week=week, policy_version=policy_version, _batch=batch_context)
                    rows.append(row)
                    if player.id in prior_values:
                        if row.value==prior_values[player.id]:
                            recomputed_unchanged+=1
                        else:
                            changes.append({"player_id":player.id,"week":row.week,"prior_value":prior_values[player.id],"new_value":row.value})
            except Exception as exc:
                failures.append({"player_id": player.id, "error": type(exc).__name__, "reason": str(exc)[:180]})
    position_at_cutoff = lambda row: (row.input_context_json or {}).get("position",db.get(Player,row.player_id).position).upper()
    for position in {position_at_cutoff(row) for row in rows}:
        position_rows = [row for row in rows if position_at_cutoff(row)==position]
        for rank, row in enumerate(sorted(position_rows, key=lambda item: (-item.value, item.player_id)), start=1):
            row.positional_value_rank = rank
    coverage = {"metric": "value", "input_fingerprint": fingerprint, "eligible": eligible_count, "calculated": len(rows), "low_confidence": sum(row.confidence < 0.7 for row in rows), "missing_rating": missing, "failures": failures,"changes":changes,"recomputed_unchanged":recomputed_unchanged}
    db.flush()
    coverage["output_fingerprint"] = chart_output_fingerprint(db, season=season, week=week, metric="value")
    run.status = "partial" if failures or missing else "complete"
    run.completed_at, run.coverage_json = _utcnow(), coverage
    db.flush()
    return {**coverage, "status": run.status, "run_id": run.id}
