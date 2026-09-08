"""Auditable Nebraska RB depth and player-data correction for Jamal Rule.

The original 2026 source snapshot omitted Rule, so this correction explicitly
adds only his exact ESPN identity to the eligible pool. It never promotes a
generic provider import into draft or waiver eligibility.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.integrations.espn import extract_player_box_score_stats
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_role_snapshot import PlayerRoleSnapshot
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.services.espn_player_lookup import persist_espn_player_profile
from collegefootballfantasy_api.app.services.espn_stats_sync import (
    persist_final_espn_player_game_stats,
    persist_normalized_espn_player_stats,
)
from collegefootballfantasy_api.app.services.player_pool_filters import (
    CANONICAL_CORRECTION_SOURCE_PREFIX,
    LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX,
)
from collegefootballfantasy_api.app.services.provider_identity import upsert_player_provider_mapping
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points


JAMAL_RULE_NAME = "Jamal Rule"
JAMAL_RULE_SCHOOL = "Nebraska"
JAMAL_RULE_POSITION = "RB"
JAMAL_RULE_ESPN_ID = "5290565"
NEBRASKA_WEEK_ONE_EVENT_ID = "401858430"
CORRECTION_SOURCE = "editorial_depth_chart_correction"
CORRECTION_MARKER = "jamal-rule-nebraska-week1"
ESPN_BOX_SCORE_URL = (
    "https://www.espn.com/college-football/boxscore/_/gameId/401858430"
)
ESPN_PROFILE_URL = "https://www.espn.com/college-football/player/_/id/5290565/jamal-rule"

# This is a conservative role projection, not a claimed ESPN forecast. It is
# deliberately below a full-season extrapolation of Rule's 36.9-point debut
# and keeps the player usable in the published pool until normal weekly
# post-final forecasting has enough games to take over.
JAMAL_RULE_SEASON_PROJECTION = {
    "rush_yards": 1040.0,
    "rush_tds": 12.0,
    "receptions": 22.0,
    "rec_yards": 280.0,
    "rec_tds": 3.0,
}


def _identity(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _one_player(db: Session, *, name: str) -> Player:
    matches = db.scalars(
        select(Player).where(
            Player.name == name,
            Player.school == JAMAL_RULE_SCHOOL,
            Player.position == JAMAL_RULE_POSITION,
        )
    ).all()
    if len(matches) > 1:
        raise ValueError(f"Ambiguous Nebraska RB records for {name}.")
    if len(matches) == 1:
        return matches[0]
    player = Player(name=name, school=JAMAL_RULE_SCHOOL, position=JAMAL_RULE_POSITION)
    db.add(player)
    db.flush()
    return player


def _profile_is_exact_rule(profile: dict[str, Any]) -> bool:
    athlete = profile.get("athlete") if isinstance(profile, dict) else None
    if not isinstance(athlete, dict):
        return False
    team = athlete.get("team") if isinstance(athlete.get("team"), dict) else {}
    position = athlete.get("position") if isinstance(athlete.get("position"), dict) else {}
    return (
        str(athlete.get("id") or "") == JAMAL_RULE_ESPN_ID
        and _identity(athlete.get("displayName") or athlete.get("name")) == _identity(JAMAL_RULE_NAME)
        and _identity(position.get("abbreviation") or position.get("displayName")) == "rb"
        and any(
            _identity(team.get(key)) == "nebraska"
            for key in ("location", "displayName", "shortDisplayName", "name")
        )
    )


def _final_summary_for_event(summary: dict[str, Any]) -> bool:
    header = summary.get("header") if isinstance(summary, dict) else None
    if not isinstance(header, dict) or str(header.get("id") or "") != NEBRASKA_WEEK_ONE_EVENT_ID:
        return False
    competitions = header.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return False
    status = competitions[0].get("status") if isinstance(competitions[0], dict) else None
    status_type = status.get("type") if isinstance(status, dict) and isinstance(status.get("type"), dict) else {}
    return bool(status_type.get("completed")) or str(status_type.get("name") or "").upper() == "STATUS_FINAL"


def _rule_week_one_stats(summary: dict[str, Any]) -> dict[str, Any]:
    matches = [
        row
        for row in extract_player_box_score_stats(summary)
        if str(row.get("ESPNPlayerID") or "") == JAMAL_RULE_ESPN_ID
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one Jamal Rule row in Nebraska's Week 1 ESPN box score.")
    stats = dict(matches[0])
    if (
        _identity(stats.get("PlayerName")) != _identity(JAMAL_RULE_NAME)
        or _identity(stats.get("School")) != "nebraska"
        or str(stats.get("EventID") or "") != NEBRASKA_WEEK_ONE_EVENT_ID
    ):
        raise ValueError("Jamal Rule's ESPN box score identity did not match Nebraska Week 1.")
    expected = {
        "rushing_attempts": 15.0,
        "rush_yards": 122.0,
        "rush_tds": 2.0,
        "receptions": 2.0,
        "rec_yards": 47.0,
        "rec_tds": 1.0,
    }
    for key, value in expected.items():
        if float(stats.get(key) or 0.0) != value:
            raise ValueError(f"Unexpected Jamal Rule Week 1 {key}: {stats.get(key)!r}.")
    return stats


def _upsert_role_snapshot(
    db: Session,
    *,
    player: Player,
    season: int,
    week: int,
    depth_order: int,
    role_status: str,
) -> None:
    snapshot = db.scalar(
        select(PlayerRoleSnapshot).where(
            PlayerRoleSnapshot.player_id == player.id,
            PlayerRoleSnapshot.season == season,
            PlayerRoleSnapshot.week == week,
        )
    )
    if snapshot is None:
        snapshot = PlayerRoleSnapshot(
            player_id=player.id,
            season=season,
            week=week,
            school=JAMAL_RULE_SCHOOL,
            position=JAMAL_RULE_POSITION,
        )
        db.add(snapshot)
    snapshot.source = CORRECTION_SOURCE
    snapshot.school = JAMAL_RULE_SCHOOL
    snapshot.position = JAMAL_RULE_POSITION
    snapshot.depth_order = depth_order
    snapshot.role_status = role_status


def apply_jamal_rule_nebraska_correction(
    db: Session,
    *,
    season: int,
    role_weeks: Iterable[int],
    profile: dict[str, Any],
    week_one_summary: dict[str, Any],
) -> dict[str, Any]:
    """Create/update the one verified player and correct Nebraska's RB order.

    The caller owns the transaction. The operation is idempotent and refuses
    to write if either ESPN payload is not the exact, completed Week 1 record.
    """

    if not _profile_is_exact_rule(profile):
        raise ValueError("ESPN profile is not the exact Jamal Rule / Nebraska / RB identity.")
    if not _final_summary_for_event(week_one_summary):
        raise ValueError("Nebraska Week 1 ESPN event is not an accepted final summary.")
    stats = _rule_week_one_stats(week_one_summary)
    game = db.scalar(
        select(Game).where(
            Game.external_id == NEBRASKA_WEEK_ONE_EVENT_ID,
            Game.season == season,
            Game.week == 1,
        )
    )
    if game is None:
        raise ValueError("Nebraska's Week 1 game is missing from the canonical schedule.")

    rule = _one_player(db, name=JAMAL_RULE_NAME)
    mozee = _one_player(db, name="Isaiah Mozee")
    nelson = _one_player(db, name="Mekhi Nelson")
    ives = _one_player(db, name="Kwinten Ives")

    projection_stats = {
        **JAMAL_RULE_SEASON_PROJECTION,
        "fpts": calculate_fantasy_points(JAMAL_RULE_SEASON_PROJECTION, position="RB"),
        "projection_season": season,
        "scoring_policy_version": "manual_correction_week1_role_baseline_v1",
        "source_fantasy_proj": None,
    }
    rule.sheet_projected_season_points = float(projection_stats["fpts"])
    rule.sheet_projection_stats = projection_stats
    rule.sheet_source_sheet_id = f"{CANONICAL_CORRECTION_SOURCE_PREFIX}{season}:{CORRECTION_MARKER}"
    rule.sheet_synced_at = datetime.now(timezone.utc)
    rule.depth_chart_position, rule.depth_order = "RB1", 1
    rule.player_class = "Freshman"
    rule.external_id = f"espn:{JAMAL_RULE_ESPN_ID}"
    rule.espn_source_url = ESPN_PROFILE_URL
    persist_espn_player_profile(rule, profile)
    upsert_player_provider_mapping(
        db,
        player_id=rule.id,
        provider="espn",
        provider_player_id=JAMAL_RULE_ESPN_ID,
        provider_team_id="158",
        match_confidence=1.0,
        verification_status="verified",
        reason="Exact ESPN Nebraska roster/profile and completed Week 1 box-score match for Jamal Rule.",
    )

    mozee.depth_chart_position, mozee.depth_order = "RB2", 2
    nelson.depth_chart_position, nelson.depth_order = "RB3", 3
    # Preserve any historical foreign keys while removing the displaced RB3
    # from all current draft/waiver/rank surfaces.
    ives.depth_chart_position, ives.depth_order = None, None
    source_marker = (ives.sheet_source_sheet_id or "").strip()
    if not source_marker.startswith(LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX):
        ives.sheet_source_sheet_id = (
            f"{LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX}{season}:{CORRECTION_MARKER}:{source_marker or 'previously-unmarked'}"
        )

    effective_weeks = sorted({int(week) for week in role_weeks if 1 <= int(week) <= 13})
    if not effective_weeks:
        raise ValueError("Nebraska RB correction requires at least one regular-season week.")
    for week in effective_weeks:
        _upsert_role_snapshot(db, player=rule, season=season, week=week, depth_order=1, role_status="starter")
        _upsert_role_snapshot(db, player=mozee, season=season, week=week, depth_order=2, role_status="rotation")
        _upsert_role_snapshot(db, player=nelson, season=season, week=week, depth_order=3, role_status="rotation")

    normalized = [{"player_id": rule.id, "stats": stats}]
    persist_normalized_espn_player_stats(db, season=season, week=1, normalized_rows=normalized)
    # Some operational sessions intentionally run with autoflush disabled.
    # Flush the newly promoted compatibility row before retrieving it for the
    # final-source/verification upgrade below.
    db.flush()
    weekly = db.scalar(
        select(PlayerStat).where(
            PlayerStat.player_id == rule.id,
            PlayerStat.season == season,
            PlayerStat.week == 1,
        )
    )
    assert weekly is not None
    weekly.source = "espn_final_boxscore"
    weekly.verified = True
    persist_final_espn_player_game_stats(
        db,
        season=season,
        week=1,
        game_id=game.id,
        normalized_rows=normalized,
    )
    game.schedule_status = "final"

    return {
        "player_id": rule.id,
        "player": rule.name,
        "espn_player_id": JAMAL_RULE_ESPN_ID,
        "event_id": NEBRASKA_WEEK_ONE_EVENT_ID,
        "week_one_fantasy_points": calculate_fantasy_points(stats, position="RB"),
        "season_projection": rule.sheet_projected_season_points,
        "active_depth": [
            {"name": rule.name, "slot": rule.depth_chart_position},
            {"name": mozee.name, "slot": mozee.depth_chart_position},
            {"name": nelson.name, "slot": nelson.depth_chart_position},
        ],
        "retired_from_current_pool": ives.name,
        "role_weeks": effective_weeks,
    }
