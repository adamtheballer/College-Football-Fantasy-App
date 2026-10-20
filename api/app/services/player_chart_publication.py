"""Publish chart history from canonical verified stats after weekly finality.

This writes no matchup, league score or standing. Card reads never run it.
"""
from datetime import datetime, timezone
import hashlib
import json
import math
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import not_, or_,func
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_chart_week import PlayerChartWeek, PlayerChartPublicationRun, PlayerChartForecast
from collegefootballfantasy_api.app.domain.stat_normalization import ALIASES_BY_PROFILE
from collegefootballfantasy_api.app.domain.scoring_rules import scoring_profile_for_position
from collegefootballfantasy_api.app.domain.scoring_engine import CALCULATION_VERSION
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points, get_scoring_rules
from collegefootballfantasy_api.app.services.fantasy_week_finality import week_is_authoritatively_finalized
from collegefootballfantasy_api.app.services.player_pool_filters import approved_school_player_filter, generated_test_player_filter, retired_canonical_preseason_player_filter, ELIGIBLE_FANTASY_POSITIONS
from collegefootballfantasy_api.app.services.fantasy_game_selection import fantasy_stat_weeks


@dataclass(frozen=True)
class ChartStatInput:
    player_id: int
    id: int | None
    week: int
    source: str
    stats: dict
    updated_at: datetime | None = None


def verified_fantasy_week_stats(db: Session, *, season: int, week: int, players: list[Player], final_games_only: bool = False) -> dict[int,ChartStatInput]:
    source_weeks = fantasy_stat_weeks(db,season=season,week=week,player_ids={p.id for p in players},player_schools={p.id:p.school for p in players})
    # Player history can become final before unrelated leagues/weeks do.
    # Strict reads accept only the exact game's final box score, never a
    # verified weekly/live aggregate alone.
    result = {} if final_games_only else {row.player_id:ChartStatInput(row.player_id,row.id,row.week,row.source,row.stats,row.updated_at) for row in db.query(PlayerStat).filter(PlayerStat.player_id.in_(source_weeks),PlayerStat.season==season,PlayerStat.week.in_(set(source_weeks.values())),PlayerStat.verified.is_(True)).all() if row.week==source_weeks[row.player_id]}
    from collegefootballfantasy_api.app.services.fantasy_game_selection import fantasy_games_by_school,school_key
    from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
    selected=fantasy_games_by_school(db,season=season,week=week)
    game_ids={game.id for game in selected.values() if game is not None and game.external_id and game.season_type=="regular" and (game.schedule_status or "").lower() in {"final","post"}}
    final_facts={(row.player_id,row.game_id):row for row in db.query(PlayerGameStat).filter(PlayerGameStat.player_id.in_(source_weeks),PlayerGameStat.season==season,PlayerGameStat.game_id.in_(game_ids),PlayerGameStat.source=="espn_final_boxscore").all()}
    for player in players:
        if player.id in result and points_from_verified_stats(result[player.id].stats,position=player.position) is not None:
            continue
        game=selected.get(school_key(player.school))
        fact=final_facts.get((player.id,game.id)) if game is not None else None
        if fact is not None and fact.week==source_weeks[player.id]:
            # Recover chart facts without rewriting weekly stats, matchups or
            # standings. Explicitly reject live, foreign-season and unmapped
            # games; do not sum two different games into one fantasy week.
            result[player.id]=ChartStatInput(player.id,None,fact.week,fact.source,{**fact.stats,"_chart_game_stat_id":fact.id,"_chart_provider_game_id":game.external_id},fact.updated_at)
    return result


def points_from_verified_stats(stats: dict, *, position: str, rules: dict | None = None) -> float | None:
    if not stats or stats.get("_scoring_incomplete"):
        return None
    profile_aliases = ALIASES_BY_PROFILE.get(scoring_profile_for_position(position), {})
    profile_keys = {alias for group in profile_aliases.values() for alias in group}
    if any(key in profile_keys and (not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value)) for key,value in stats.items()):
        return None
    has_raw = any(key in profile_keys and isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for key, value in stats.items())
    if has_raw:
        result = calculate_fantasy_points(stats, rules_bundle=rules, position=position)
        return result if math.isfinite(result) else None
    # Legacy canonical FPTS-only records can support standard history, but
    # cannot be rescored under a different league's rules.
    from collegefootballfantasy_api.app.services.projection_scoring import is_standard_scoring
    if is_standard_scoring(rules,position):
        for key in ("fantasy_points", "fantasyPoints", "fpts"):
            value = stats.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
                return float(value)
    return None

def eligible_chart_players_query(db: Session, season: int):
    return db.query(Player).filter(approved_school_player_filter(), generated_test_player_filter(), or_(Player.sheet_source_sheet_id.is_(None), not_(retired_canonical_preseason_player_filter(season))), func.upper(Player.position).in_(ELIGIBLE_FANTASY_POSITIONS))

def chart_input_fingerprint(db: Session, *, season: int, week: int, metric: str) -> str:
    from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
    from collegefootballfantasy_api.app.models.injury import Injury
    players = eligible_chart_players_query(db, season).order_by(Player.id).all()
    ids = [player.id for player in players]
    peers = db.query(Player).order_by(Player.id).all() if metric == "value" else players
    facts = [(row.player_id, row.week, row.verified, row.stats) for row in db.query(PlayerStat).filter(PlayerStat.player_id.in_([p.id for p in peers]), PlayerStat.season == season, PlayerStat.week.between(0 if metric == "value" or week==1 else week, max(week, 1))).order_by(PlayerStat.player_id, PlayerStat.week).all()]
    payload = {"metric": metric, "season": season, "week": week, "players": [(p.id,p.position,p.school) for p in players], "facts": facts, "scoring": get_scoring_rules(), "version": CALCULATION_VERSION}
    payload["publisher_version"] = "chart-facts-v3-pregame-capture"
    if metric=="actual":
        payload["original_forecasts"] = [(r.player_id,r.snapshot_json) for r in db.query(PlayerChartForecast).filter_by(season=season,week=week).order_by(PlayerChartForecast.player_id).all()]
    payload["opening_source_weeks"] = sorted(fantasy_stat_weeks(db,season=season,week=1,player_ids={p.id for p in peers},player_schools={p.id:p.school for p in peers}).items())
    from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
    from collegefootballfantasy_api.app.models.game import Game
    first_week=0 if metric=="value" or week==1 else week
    payload["final_game_facts"]=[(r.id,r.player_id,r.game_id,r.week,r.stats) for r in db.query(PlayerGameStat).filter(PlayerGameStat.player_id.in_([p.id for p in peers]),PlayerGameStat.season==season,PlayerGameStat.week.between(first_week,max(week,1)),PlayerGameStat.source=="espn_final_boxscore").order_by(PlayerGameStat.id).all()]
    payload["game_selection"]=[(r.id,r.external_id,r.week,r.home_team,r.away_team,r.start_date,r.schedule_status,r.season_type) for r in db.query(Game).filter(Game.season==season,Game.week.between(first_week,max(week,1))).order_by(Game.id).all()]
    if metric == "value":
        payload["policy"] = "weekly-stats-projections-v4-cutoff-eligible"
        payload["baselines"] = [(p.id, p.position, p.raw_cfb27_rating, p.sheet_projected_season_points) for p in peers]
        payload["finalized_weeks"] = [w for w in range(1,max(week,1)+1) if week_is_authoritatively_finalized(db,season=season,week=w)]
        payload["durable_facts"] = [(r.player_id,r.week,r.input_hash) for r in db.query(PlayerChartWeek).filter(PlayerChartWeek.season==season,PlayerChartWeek.week.between(1,max(week,1))).order_by(PlayerChartWeek.player_id,PlayerChartWeek.week).all()]
        payload["projections"] = [(row.player_id, row.projection_version, row.is_published, row.fantasy_points) for row in db.query(WeeklyProjection).filter(WeeklyProjection.season == season, WeeklyProjection.week == max(week, 1)).order_by(WeeklyProjection.id).all()]
        payload["injuries"] = [(row.player_id, row.week, row.status, row.return_timeline, row.is_returning) for row in db.query(Injury).filter(Injury.season == season, Injury.week <= max(week, 1)).order_by(Injury.id).all()]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def chart_output_fingerprint(db: Session, *, season: int, week: int, metric: str) -> str:
    from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
    if metric == "actual":
        output = [(row.player_id, row.input_hash, row.standard_points, row.stats_json, row.scoring_rules_json) for row in db.query(PlayerChartWeek).filter_by(season=season, week=week).order_by(PlayerChartWeek.player_id).all()]
    else:
        output = [(row.player_id, row.week, row.policy_version, row.value, row.factor_breakdown_json, row.input_context_json,row.positional_value_rank,row.weekly_change,row.confidence,row.tier) for row in db.query(PlayerTradeValue).filter(PlayerTradeValue.season == season, PlayerTradeValue.week.in_([0, week])).order_by(PlayerTradeValue.player_id, PlayerTradeValue.week, PlayerTradeValue.policy_version).all()]
    return hashlib.sha256(json.dumps(output, sort_keys=True, default=str).encode()).hexdigest()


def previous_chart_run(db: Session, *, season: int, week: int, metric: str, fingerprint: str):
    previous = db.query(PlayerChartPublicationRun).filter(PlayerChartPublicationRun.season == season, PlayerChartPublicationRun.week == week, PlayerChartPublicationRun.coverage_json["metric"].as_string() == metric).order_by(PlayerChartPublicationRun.id.desc()).first()
    if previous and previous.coverage_json.get("input_fingerprint") == fingerprint and not previous.coverage_json.get("failures") and previous.coverage_json.get("output_fingerprint") == chart_output_fingerprint(db, season=season, week=week, metric=metric):
        return previous
    return None


def publish_finalized_chart_week(db: Session, *, season: int, week: int, batch_size: int = 200) -> dict:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    db.flush()
    if not 1 <= week <= 13 or not week_is_authoritatively_finalized(db, season=season, week=week):
        return {"status": "waiting_for_finality", "actuals": 0}
    from collegefootballfantasy_api.app.services.chart_forecasts import capture_started_chart_forecasts
    forecast_capture = capture_started_chart_forecasts(db,season=season,week=week,batch_size=batch_size)
    fingerprint = chart_input_fingerprint(db, season=season, week=week, metric="actual")
    previous = previous_chart_run(db, season=season, week=week, metric="actual", fingerprint=fingerprint)
    if previous:
        return {**previous.coverage_json, "forecast_capture":forecast_capture, "unchanged": previous.coverage_json["actuals"], "status": previous.status, "run_id": previous.id}
    run = PlayerChartPublicationRun(season=season, week=week, status="running", started_at=datetime.now(timezone.utc), coverage_json={})
    db.add(run); db.flush()
    coverage = {"metric": "actual", "input_fingerprint": fingerprint, "eligible": 0, "actuals": 0, "unchanged": 0, "missing_stats": [], "failures": [], "corrections": [], "forecast_capture":forecast_capture, "forecast_recoveries":[]}
    last_id = 0
    rules = get_scoring_rules()
    while True:
        players = eligible_chart_players_query(db, season).filter(Player.id > last_id).order_by(Player.id).limit(batch_size).all()
        if not players:
            break
        last_id = players[-1].id
        stats_by_id = verified_fantasy_week_stats(db,season=season,week=week,players=players)
        forecasts_by_id = {r.player_id:r.snapshot_json for r in db.query(PlayerChartForecast).filter(PlayerChartForecast.player_id.in_([p.id for p in players]),PlayerChartForecast.season==season,PlayerChartForecast.week==week).all()}
        for player in players:
            coverage["eligible"] += 1
            try:
                with db.begin_nested():
                    source = stats_by_id.get(player.id)
                    row = db.query(PlayerChartWeek).filter_by(player_id=player.id, season=season, week=week).with_for_update().one_or_none()
                    scoring_position = (row.stats_json or {}).get("_chart_position", player.position) if row else player.position
                    snapshot_rules = row.scoring_rules_json if row else rules
                    points = points_from_verified_stats(source.stats if source else {}, position=scoring_position,rules=snapshot_rules)
                    if points is None:
                        coverage["missing_stats"].append(player.id)
                        continue
                    context = {"stats": source.stats, "source_week": source.week, "source_stat_id": source.id, "position": scoring_position, "rules": snapshot_rules, "version": CALCULATION_VERSION}
                    digest = hashlib.sha256(json.dumps(context, sort_keys=True, allow_nan=False).encode()).hexdigest()
                    if row and row.input_hash == digest:
                        coverage["unchanged"] += 1
                        if not row.stats_json.get("_chart_forecast") and player.id in forecasts_by_id:
                            row.stats_json = {**row.stats_json,"_chart_forecast":forecasts_by_id[player.id]}
                            coverage["forecast_recoveries"].append(player.id)
                    else:
                        if row is not None:
                            coverage["corrections"].append({"player_id": player.id, "prior_input_hash": row.input_hash, "prior_points": row.standard_points, "new_input_hash": digest, "new_points": points})
                        if row is None:
                            row = PlayerChartWeek(player_id=player.id, season=season, week=week)
                            db.add(row)
                        # Preserve the original comparison through later stat,
                        # forecast, school or position corrections. A missing
                        # original can be enriched only from evidenced pregame
                        # inputs, never from a retrospective estimate.
                        forecast = (row.stats_json or {}).get("_chart_forecast") or forecasts_by_id.get(player.id)
                        row.stats_json, row.standard_points, row.scoring_rules_json = {**source.stats, "_chart_position": scoring_position, "_chart_forecast": forecast}, points, snapshot_rules
                        row.input_hash, row.source_stat_id = digest, source.id
                        row.finalized_at, row.calculation_version = datetime.now(timezone.utc), CALCULATION_VERSION
                    coverage["actuals"] += 1
            except Exception as exc:
                coverage["failures"].append({"player_id": player.id, "error": type(exc).__name__})
    db.flush()
    coverage["output_fingerprint"] = chart_output_fingerprint(db, season=season, week=week, metric="actual")
    run.status = "partial" if coverage["failures"] or coverage["missing_stats"] else "complete"
    run.completed_at, run.coverage_json = datetime.now(timezone.utc), coverage
    db.flush()
    return {"status": run.status, **coverage, "run_id": run.id}
