"""One-time correction for retiring punt-return production from CFFB.

The scoring contract now excludes punt returns.  This service makes the
policy durable for existing data by removing legacy provider fields before
recalculating every persisted fantasy artifact that could have used them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.stat_normalization import (
    strip_unscored_return_stats,
)
from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points
from collegefootballfantasy_api.app.services.scoring_service import recalculate_league_week_scores
from collegefootballfantasy_api.app.services.weekly_outlook_refresh import refresh_post_final_outlook


_RETIRED_SCORING_RULE_KEYS = frozenset({
    "puntreturnyards",
    "puntreturntouchdowns",
    "puntreturntd",
    "puntreturntds",
    "puntreturnyardsperpoint",
})
_HISTORICAL_RETURN_FIELDS = (
    "punt_return_attempts",
    "punt_return_yards",
    "punt_return_touchdowns",
)


def _canonical_key(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def strip_retired_punt_return_rules(value: Any) -> Any:
    """Remove retired punt-return settings from flat or profile scoring JSON."""

    if isinstance(value, Mapping):
        return {
            str(key): strip_retired_punt_return_rules(child)
            for key, child in value.items()
            if _canonical_key(key) not in _RETIRED_SCORING_RULE_KEYS
        }
    if isinstance(value, list):
        return [strip_retired_punt_return_rules(child) for child in value]
    return value


@dataclass(frozen=True)
class PuntReturnPolicyCorrectionSummary:
    player_stats_sanitized: int
    game_stats_sanitized: int
    historical_rows_sanitized: int
    league_settings_sanitized: int
    league_weeks_recalculated: int
    outlook_refreshes: int


def apply_punt_return_policy_correction(db: Session) -> PuntReturnPolicyCorrectionSummary:
    """Sanitize legacy rows and recalculate all affected CFFB-derived values.

    The operation is deliberately idempotent so it is safe in an Alembic
    upgrade and in a deployment recovery run. Provider raw-payload audit
    snapshots are left intact; only public/canonical player stats are changed.
    """

    player_stats_sanitized = 0
    game_stats_sanitized = 0
    historical_rows_sanitized = 0
    league_settings_sanitized = 0

    for row in db.scalars(select(PlayerStat)).all():
        cleaned = strip_unscored_return_stats(
            row.stats,
            remove_derived_fantasy_points=True,
        )
        if cleaned != (row.stats or {}):
            row.stats = cleaned
            player_stats_sanitized += 1

    for row in db.scalars(select(PlayerGameStat)).all():
        cleaned = strip_unscored_return_stats(
            row.stats,
            remove_derived_fantasy_points=True,
        )
        if cleaned != (row.stats or {}):
            row.stats = cleaned
            game_stats_sanitized += 1

    for row in db.scalars(select(PlayerHistoricalSeasonStat)).all():
        changed = False
        for field in _HISTORICAL_RETURN_FIELDS:
            if getattr(row, field) is not None:
                setattr(row, field, None)
                changed = True
        recalculated = calculate_fantasy_points(
            {
                "pass_yards": row.passing_yards,
                "pass_tds": row.passing_touchdowns,
                "interceptions": row.interceptions,
                "rush_yards": row.rushing_yards,
                "rush_tds": row.rushing_touchdowns,
                "receptions": row.receptions,
                "rec_yards": row.receiving_yards,
                "rec_tds": row.receiving_touchdowns,
                "fumbles_lost": row.fumbles_lost,
                "fg_made_0_39": sum(value or 0 for value in (
                    row.field_goals_0_19,
                    row.field_goals_20_29,
                    row.field_goals_30_39,
                )),
                "fg_made_40_49": row.field_goals_40_49,
                "fg_made_50_plus": row.field_goals_50_plus,
                "xp_made": row.extra_points_made,
            },
            position=row.canonical_position or row.position,
        )
        recalculated_per_game = (
            round(recalculated / row.games_played, 2)
            if row.games_played and row.games_played > 0
            else None
        )
        if row.fantasy_points != recalculated or row.fantasy_points_per_game != recalculated_per_game:
            row.fantasy_points = recalculated
            row.fantasy_points_per_game = recalculated_per_game
            changed = True
        if changed:
            historical_rows_sanitized += 1

    # This correction is executed by migration 0115. Select only the two
    # columns that existed at that migration's schema point: importing the
    # current ORM model must not make an older migration select a future
    # column before the later migration that creates it has run.
    for league_id, scoring_json in db.execute(
        select(LeagueSettings.id, LeagueSettings.scoring_json)
    ):
        cleaned = strip_retired_punt_return_rules(scoring_json or {})
        if cleaned != (scoring_json or {}):
            db.execute(
                update(LeagueSettings)
                .where(LeagueSettings.id == league_id)
                .values(scoring_json=cleaned)
            )
            league_settings_sanitized += 1

    db.flush()

    score_scopes = db.execute(
        select(
            PlayerWeekScore.league_id,
            PlayerWeekScore.season,
            PlayerWeekScore.week,
        ).distinct()
    ).all()
    league_weeks_recalculated = 0
    for league_id, season, week in score_scopes:
        # A score row without a canonical player stat cannot be safely
        # rewritten by the league scorer; its game-log fallback remains
        # correctly recalculated at read time under the new policy.
        has_canonical_stats = db.scalar(
            select(PlayerStat.id).where(
                PlayerStat.season == season,
                PlayerStat.week == week,
            ).limit(1)
        )
        if has_canonical_stats is None:
            continue
        recalculate_league_week_scores(db, int(league_id), int(season), int(week))
        league_weeks_recalculated += 1

    outlook_refreshes = 0
    stat_scopes = db.execute(
        select(PlayerStat.season, PlayerStat.week)
        .where(PlayerStat.week >= 0)
        .distinct()
    ).all()
    for season, week in stat_scopes:
        result = refresh_post_final_outlook(db, season=int(season), completed_week=int(week))
        if result.get("status") == "refreshed":
            outlook_refreshes += 1

    db.flush()
    return PuntReturnPolicyCorrectionSummary(
        player_stats_sanitized=player_stats_sanitized,
        game_stats_sanitized=game_stats_sanitized,
        historical_rows_sanitized=historical_rows_sanitized,
        league_settings_sanitized=league_settings_sanitized,
        league_weeks_recalculated=league_weeks_recalculated,
        outlook_refreshes=outlook_refreshes,
    )
