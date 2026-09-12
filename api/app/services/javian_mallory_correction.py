"""Auditable Miami RB3 correction for verified freshman Javian Mallory.

The reviewed preseason snapshot named Girard Pringle Jr. as Miami's RB3.  A
provider import alone is never enough to make a player draftable or claimable,
so this correction promotes only ESPN's exact Javian Mallory record and retains
the displaced record for historical foreign-key safety.
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
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
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


JAVIAN_MALLORY_NAME = "Javian Mallory"
JAVIAN_MALLORY_SCHOOL = "Miami"
JAVIAN_MALLORY_POSITION = "RB"
JAVIAN_MALLORY_ESPN_ID = "5160496"
MIAMI_ESPN_TEAM_ID = "2390"
MIAMI_WEEK_TWO_EVENT_ID = "401858213"
OBSOLETE_RB3_NAME = "Girard Pringle Jr."
CORRECTION_SOURCE = "editorial_depth_chart_correction"
CORRECTION_MARKER = "javian-mallory-miami-rb3-week2"
ESPN_PROFILE_URL = "https://www.espn.com/college-football/player/_/id/5160496/javian-mallory"

# This is a conservative role baseline, not an ESPN forecast and not a
# full-season extrapolation of Mallory's 10/142/2 debut.  Normal post-final
# outlook refreshes can supersede it as more verified games are available.
JAVIAN_MALLORY_SEASON_PROJECTION = {
    "rush_yards": 730.0,
    "rush_tds": 7.0,
    "receptions": 15.0,
    "rec_yards": 135.0,
    "rec_tds": 1.0,
}


def _identity(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _one_player(db: Session, *, name: str) -> Player:
    matches = db.scalars(
        select(Player).where(
            Player.name == name,
            Player.school == JAVIAN_MALLORY_SCHOOL,
            Player.position == JAVIAN_MALLORY_POSITION,
        )
    ).all()
    if len(matches) > 1:
        raise ValueError(f"Ambiguous Miami RB records for {name}.")
    if matches:
        return matches[0]
    player = Player(name=name, school=JAVIAN_MALLORY_SCHOOL, position=JAVIAN_MALLORY_POSITION)
    db.add(player)
    db.flush()
    return player


def _profile_is_exact_mallory(profile: dict[str, Any]) -> bool:
    athlete = profile.get("athlete") if isinstance(profile, dict) else None
    if not isinstance(athlete, dict):
        return False
    team = athlete.get("team") if isinstance(athlete.get("team"), dict) else {}
    position = athlete.get("position") if isinstance(athlete.get("position"), dict) else {}
    return (
        str(athlete.get("id") or "") == JAVIAN_MALLORY_ESPN_ID
        and _identity(athlete.get("displayName") or athlete.get("name")) == _identity(JAVIAN_MALLORY_NAME)
        and _identity(position.get("abbreviation") or position.get("displayName")) == "rb"
        and any(
            _identity(team.get(key)) in {"miami", "miamihurricanes"}
            for key in ("location", "displayName", "shortDisplayName", "name")
        )
    )


def _final_summary_for_event(summary: dict[str, Any]) -> bool:
    header = summary.get("header") if isinstance(summary, dict) else None
    if not isinstance(header, dict) or str(header.get("id") or "") != MIAMI_WEEK_TWO_EVENT_ID:
        return False
    if int((header.get("week") or 0)) != 2:
        return False
    competitions = header.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return False
    status = competitions[0].get("status") if isinstance(competitions[0], dict) else None
    status_type = status.get("type") if isinstance(status, dict) and isinstance(status.get("type"), dict) else {}
    return bool(status_type.get("completed")) or str(status_type.get("name") or "").upper() == "STATUS_FINAL"


def _mallory_week_two_stats(summary: dict[str, Any]) -> dict[str, Any]:
    matches = [
        row
        for row in extract_player_box_score_stats(summary)
        if str(row.get("ESPNPlayerID") or "") == JAVIAN_MALLORY_ESPN_ID
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one Javian Mallory row in Miami's Week 2 ESPN box score.")
    stats = dict(matches[0])
    if (
        _identity(stats.get("PlayerName")) != _identity(JAVIAN_MALLORY_NAME)
        or _identity(stats.get("School")) not in {"miami", "miamihurricanes"}
        or str(stats.get("EventID") or "") != MIAMI_WEEK_TWO_EVENT_ID
    ):
        raise ValueError("Javian Mallory's ESPN box-score identity did not match Miami Week 2.")
    expected = {"rushing_attempts": 10.0, "rush_yards": 142.0, "rush_tds": 2.0}
    for key, value in expected.items():
        if float(stats.get(key) or 0.0) != value:
            raise ValueError(f"Unexpected Javian Mallory Week 2 {key}: {stats.get(key)!r}.")
    return stats


def _upsert_role_snapshot(db: Session, *, player: Player, season: int, week: int) -> None:
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
            school=JAVIAN_MALLORY_SCHOOL,
            position=JAVIAN_MALLORY_POSITION,
        )
        db.add(snapshot)
    snapshot.source = CORRECTION_SOURCE
    snapshot.school = JAVIAN_MALLORY_SCHOOL
    snapshot.position = JAVIAN_MALLORY_POSITION
    snapshot.depth_order = 3
    snapshot.role_status = "rotation"


def apply_javian_mallory_miami_correction(
    db: Session,
    *,
    season: int,
    role_weeks: Iterable[int],
    profile: dict[str, Any],
    week_two_summary: dict[str, Any],
) -> dict[str, Any]:
    """Promote only verified Mallory data and retire Miami's old RB3.

    The caller owns the transaction.  This is idempotent and refuses to write
    unless ESPN verifies both the player identity and completed Week 2 result.
    """

    if not _profile_is_exact_mallory(profile):
        raise ValueError("ESPN profile is not the exact Javian Mallory / Miami / RB identity.")
    if not _final_summary_for_event(week_two_summary):
        raise ValueError("Miami Week 2 ESPN event is not an accepted final summary.")
    stats = _mallory_week_two_stats(week_two_summary)
    game = db.scalar(
        select(Game).where(
            Game.external_id == MIAMI_WEEK_TWO_EVENT_ID,
            Game.season == season,
            Game.week == 2,
        )
    )
    if game is None:
        raise ValueError("Miami's Week 2 game is missing from the canonical schedule.")

    mallory = _one_player(db, name=JAVIAN_MALLORY_NAME)
    pringle = _one_player(db, name=OBSOLETE_RB3_NAME)
    projection_stats = {
        **JAVIAN_MALLORY_SEASON_PROJECTION,
        "fpts": calculate_fantasy_points(JAVIAN_MALLORY_SEASON_PROJECTION, position="RB"),
        "projection_season": season,
        "scoring_policy_version": "manual_correction_week2_role_baseline_v1",
        "source_fantasy_proj": None,
    }
    mallory.sheet_projected_season_points = float(projection_stats["fpts"])
    mallory.sheet_projection_stats = projection_stats
    mallory.sheet_source_sheet_id = f"{CANONICAL_CORRECTION_SOURCE_PREFIX}{season}:{CORRECTION_MARKER}"
    mallory.sheet_synced_at = datetime.now(timezone.utc)
    mallory.depth_chart_position, mallory.depth_order = "RB3", 3
    mallory.external_id = f"espn:{JAVIAN_MALLORY_ESPN_ID}"
    mallory.espn_source_url = ESPN_PROFILE_URL
    persist_espn_player_profile(mallory, profile)
    athlete = profile.get("athlete") if isinstance(profile, dict) else None
    if isinstance(athlete, dict):
        # ESPN labels this field ``displayExperience`` rather than a player
        # class. Store it explicitly so a freshman's card is not blank.
        player_class = str(athlete.get("displayExperience") or "").strip()
        if player_class:
            mallory.player_class = player_class
    upsert_player_provider_mapping(
        db,
        player_id=mallory.id,
        provider="espn",
        provider_player_id=JAVIAN_MALLORY_ESPN_ID,
        provider_team_id=MIAMI_ESPN_TEAM_ID,
        match_confidence=1.0,
        verification_status="verified",
        reason="Exact ESPN Miami roster/profile and completed Week 2 box-score match for Javian Mallory.",
    )

    # Keep historical references intact, but exclude the displaced source-only
    # player from every current waiver, draft, and ranking surface.
    pringle.depth_chart_position, pringle.depth_order = None, None
    source_marker = (pringle.sheet_source_sheet_id or "").strip()
    if not source_marker.startswith(LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX):
        pringle.sheet_source_sheet_id = (
            f"{LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX}{season}:{CORRECTION_MARKER}:"
            f"{source_marker or 'previously-unmarked'}"
        )

    effective_weeks = sorted({int(week) for week in role_weeks if 1 <= int(week) <= 13})
    if not effective_weeks:
        raise ValueError("Miami RB correction requires at least one regular-season week.")
    for week in effective_weeks:
        _upsert_role_snapshot(db, player=mallory, season=season, week=week)

    normalized = [{"player_id": mallory.id, "stats": stats}]
    persist_normalized_espn_player_stats(db, season=season, week=2, normalized_rows=normalized)
    db.flush()
    weekly = db.scalar(
        select(PlayerStat).where(
            PlayerStat.player_id == mallory.id,
            PlayerStat.season == season,
            PlayerStat.week == 2,
        )
    )
    assert weekly is not None
    weekly.source = "espn_final_boxscore"
    weekly.verified = True
    persist_final_espn_player_game_stats(
        db,
        season=season,
        week=2,
        game_id=game.id,
        normalized_rows=normalized,
    )
    game.schedule_status = "final"

    return {
        "player_id": mallory.id,
        "player": mallory.name,
        "espn_player_id": JAVIAN_MALLORY_ESPN_ID,
        "event_id": MIAMI_WEEK_TWO_EVENT_ID,
        "week_two_fantasy_points": calculate_fantasy_points(stats, position="RB"),
        "season_projection": mallory.sheet_projected_season_points,
        "active_depth": {"name": mallory.name, "slot": mallory.depth_chart_position},
        "retired_from_current_pool": pringle.name,
        "role_weeks": effective_weeks,
    }
