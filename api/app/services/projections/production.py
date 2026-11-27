"""Calibrate role forecasts with accepted final-game component production.

No provider I/O, score writes, or publication occurs here. Small samples retain
role priors; current availability and opponent defense apply to the observed
pace before it can influence an upcoming forecast.
"""
from __future__ import annotations

from statistics import mean

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.stat_normalization import normalize_player_stats
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points
from collegefootballfantasy_api.app.services.player_chart_publication import (
    points_from_verified_stats, verified_fantasy_week_stats,
)
from collegefootballfantasy_api.app.services.power4 import canonical_school_name, normalize_school
from collegefootballfantasy_api.app.services.projections.ranges import weighted_projection_outcomes

MODEL_VERSION = "verified_production_pace_v1"
MINIMUM_GAMES = 3
PRIOR_GAMES = 2.0
RECENT_WEIGHT = 0.4
_COMPONENTS = ("rush_yards", "rush_tds", "receptions", "rec_yards", "rec_tds")


def _school_key(value):
    return canonical_school_name(value) or normalize_school(value)


def calibrate_production_pace(
    projection: WeeklyProjection, *, player: Player, games: list[dict], defense=None,
) -> bool:
    """Blend components, then rescore and rebuild ranges as one coherent result."""
    if player.position.upper() not in {"RB", "TE"} or len(games) < MINIMUM_GAMES:
        return False
    if projection.locked_at is not None or projection.projection_status in {"BYE", "NO_GAME"}:
        return False
    health = projection.availability_multiplier
    if health is None:
        health = 1.0
    if health <= 0 or projection.projection_status in {"OUT", "IR", "OUT_FOR_SEASON"}:
        return False
    # FPTS-only history cannot reconstruct a league-rescorable stat forecast.
    usable = [normalize_player_stats(game, position=player.position) for game in games
              if not game.get('_scoring_incomplete') and any(key in game for key in (
                  'receptions', 'Receptions', 'rec_yards', 'ReceivingYards',
                  'rush_yards', 'RushingYards', 'receiving_yards', 'rushing_yards'))]
    if len(usable) < MINIMUM_GAMES:
        return False
    weight = len(usable) / (len(usable) + PRIOR_GAMES)
    recent = usable[-4:]
    pace = {key: (1 - RECENT_WEIGHT) * mean(row.get(key, 0.0) for row in usable)
            + RECENT_WEIGHT * mean(row.get(key, 0.0) for row in recent) for key in _COMPONENTS}
    modifiers = {
        'rush_yards': defense.rush_yards_multiplier if defense else 1.0,
        'rush_tds': defense.rush_td_multiplier if defense else 1.0,
        'receptions': defense.pass_catch_multiplier if defense else 1.0,
        'rec_yards': defense.pass_yards_multiplier if defense else 1.0,
        'rec_tds': defense.pass_td_multiplier if defense else 1.0,
    }
    for key in _COMPONENTS:
        observed = pace[key] * float(modifiers[key] or 1.0) * health
        setattr(projection, key, (1 - weight) * float(getattr(projection, key) or 0.0) + weight * observed)
    # Opportunity fields must describe the same output as the scoring fields.
    catch_rate = 0.72 if player.position.upper() == 'RB' else 0.68
    projection.targets = max(projection.receptions, projection.receptions / catch_rate)
    carries = [next((float(game[key]) for key in ('rushing_attempts','RushingAttempts','rush_attempts','RushAttempts')
                     if game.get(key) is not None), None) for game in games]
    known_carries = [value for value in carries if value is not None]
    if player.position.upper() == 'RB' and len(known_carries) >= MINIMUM_GAMES:
        observed = (0.6 * mean(known_carries) + 0.4 * mean(known_carries[-4:])) * health
        projection.rush_attempts = (1 - weight) * float(projection.rush_attempts or 0) + weight * observed
    projection.expected_plays = float(projection.rush_attempts or 0) + projection.targets
    projection.expected_td_per_play = (projection.rush_tds + projection.rec_tds) / max(projection.expected_plays, 1)
    projection.fantasy_points = calculate_fantasy_points(
        {key: getattr(projection, key) for key in _COMPONENTS}, position=player.position)
    outcome = weighted_projection_outcomes(projection.fantasy_points, position=player.position,
        expected_opportunities=projection.expected_plays, availability_multiplier=health)
    for key in ('floor', 'ceiling', 'boom_prob', 'bust_prob'):
        setattr(projection, key, getattr(outcome, key))
    projection.baseline_games_played = len(usable)
    projection.neutral_baseline = calculate_fantasy_points(pace, position=player.position)
    projection.baseline_source = 'verified_production_pace'
    projection.model_version = MODEL_VERSION
    projection.fallback_reason = f'{MODEL_VERSION}: {len(usable)} final games; 40% recent-four pace; current health and matchup.'
    return True


def apply_verified_production_pace(
    db: Session, *, players: list[Player], projections: list[WeeklyProjection],
    season: int, week: int, defense_by_team: dict, opponent_by_team: dict,
) -> int:
    selected = [player for player in players if player.position.upper() in {'RB', 'TE'}]
    if not selected or week <= MINIMUM_GAMES:
        return 0
    history = {player.id: [] for player in selected}
    positions = {player.id: player.position for player in selected}
    for prior_week in range(1, min(week, 14)):
        for player_id, row in verified_fantasy_week_stats(
            db, season=season, week=prior_week, players=selected, final_games_only=True,
        ).items():
            if points_from_verified_stats(row.stats, position=positions[player_id]) is not None:
                history[player_id].append(row.stats)
    opponents = {_school_key(team): opponent for team, opponent in opponent_by_team.items()}
    defenses = {_school_key(team): defense for team, defense in defense_by_team.items()}
    by_id = {row.player_id: row for row in projections}
    calibrated = 0
    for player in selected:
        projection = by_id.get(player.id)
        if projection is None:
            continue
        opponent = opponents.get(_school_key(player.school))
        defense = defenses.get(_school_key(opponent)) if opponent else None
        calibrated += calibrate_production_pace(projection, player=player, games=history[player.id], defense=defense)
    return calibrated
