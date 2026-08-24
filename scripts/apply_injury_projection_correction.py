#!/usr/bin/env python3
"""Apply one auditable, provider-backed player availability correction.

This is an operator tool for a verified official/team injury update that has
not reached an automated availability provider yet.  It writes an Injury row
and a higher-priority CORRECTED_INJURY weekly projection, preserving the
underlying projection snapshots for auditability.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection


CORRECTION_VERSION = "CORRECTED_INJURY"
CORRECTION_MODEL_VERSION = "injury_override_v1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--player", required=True)
    parser.add_argument("--school", required=True)
    parser.add_argument("--status", choices=("OUT", "DOUBTFUL", "QUESTIONABLE", "PROBABLE"), required=True)
    parser.add_argument("--injury", required=True)
    parser.add_argument("--return-timeline", required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument("--apply", action="store_true", help="Persist the correction; otherwise only print the target.")
    return parser.parse_args(argv)


def _zero_projection(row: WeeklyProjection, *, status: str, note: str) -> None:
    """Make every displayed and calculated projection component consistent."""

    for column in (
        "pass_attempts", "rush_attempts", "targets", "receptions", "expected_plays",
        "expected_rush_per_play", "expected_td_per_play", "pass_yards", "rush_yards",
        "rec_yards", "pass_tds", "rush_tds", "rec_tds", "interceptions",
        "field_goals_made_0_to_39", "field_goals_made_40_to_49", "field_goals_made_0_to_49",
        "field_goals_made_50_plus", "extra_points_made", "fantasy_points", "floor", "ceiling",
        "boom_prob", "bust_prob",
    ):
        setattr(row, column, 0.0)
    row.qb_rating = None
    row.projection_status = status
    row.availability_multiplier = 0.0
    row.usage_multiplier = 1.0
    row.offense_multiplier = 1.0
    row.opponent_defense_multiplier = 1.0
    row.confidence = 1.0
    row.fallback_reason = note
    row.model_version = CORRECTION_MODEL_VERSION
    row.is_published = True
    row.locked_at = None


def apply_correction(args: argparse.Namespace) -> dict[str, object]:
    ensure_models_registered()
    with SessionLocal() as db:
        player = db.scalar(
            select(Player).where(Player.name == args.player, Player.school == args.school)
        )
        if player is None:
            raise ValueError(f"No exact player match for {args.player} ({args.school}).")

        source_projection = db.scalar(
            current_published_projections_query(
                season=args.season, week=args.week, player_ids=(player.id,)
            )
        )
        if source_projection is None:
            raise ValueError(
                f"No published Week {args.week} projection exists for {args.player}; refusing to create an unverified correction."
            )

        injury = db.scalar(
            select(Injury)
            .where(Injury.player_id == player.id, Injury.season == args.season, Injury.week == args.week)
            .order_by(Injury.updated_at.desc(), Injury.id.desc())
        )
        if injury is None:
            injury = Injury(player_id=player.id, season=args.season, week=args.week)
            db.add(injury)
        injury.status = args.status
        injury.injury = args.injury
        injury.return_timeline = args.return_timeline
        injury.practice_level = "DNP"
        injury.is_game_time_decision = False
        injury.is_returning = False
        injury.notes = args.notes

        correction = db.scalar(
            select(WeeklyProjection).where(
                WeeklyProjection.player_id == player.id,
                WeeklyProjection.season == args.season,
                WeeklyProjection.week == args.week,
                WeeklyProjection.projection_version == CORRECTION_VERSION,
            )
        )
        if correction is None:
            correction = WeeklyProjection(
                player_id=player.id,
                season=args.season,
                week=args.week,
                projection_version=CORRECTION_VERSION,
                team_id=source_projection.team_id,
                opponent_team_id=source_projection.opponent_team_id,
                neutral_baseline=source_projection.neutral_baseline,
                baseline_games_played=source_projection.baseline_games_played,
                baseline_source="official_team_availability_correction",
            )
            db.add(correction)
        _zero_projection(correction, status=args.status, note=args.notes)

        result = {
            "player_id": player.id,
            "player": player.name,
            "school": player.school,
            "season": args.season,
            "week": args.week,
            "status": args.status,
            "projection_version": CORRECTION_VERSION,
            "fantasy_points": 0.0,
            "source_projection_id": source_projection.id,
        }
        if args.apply:
            db.commit()
            result["applied_at"] = datetime.now(timezone.utc).isoformat()
        else:
            db.rollback()
            result["preview"] = True
        return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(apply_correction(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
