"""Auditable Ohio State RB3 replacement for verified freshman Legend Bey.

The reviewed preseason snapshot listed Ja'Kobi Jackson in a role that no
longer exists.  This correction replaces only that exact record after
validating Legend Bey against ESPN's current roster/profile and completed
Week 1 box score.  It intentionally refuses to delete a player with any
user-owned historical transaction rather than silently erasing league data.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.integrations.espn import extract_player_box_score_stats
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league_player_event import LeaguePlayerEvent
from collegefootballfantasy_api.app.models.mock_draft_pick import MockDraftPick
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_role_snapshot import PlayerRoleSnapshot
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.saturday_pick import SaturdayPickPlayer
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.services.espn_player_lookup import persist_espn_player_profile
from collegefootballfantasy_api.app.services.espn_stats_sync import (
    persist_final_espn_player_game_stats,
    persist_normalized_espn_player_stats,
)
from collegefootballfantasy_api.app.services.player_pool_filters import CANONICAL_CORRECTION_SOURCE_PREFIX
from collegefootballfantasy_api.app.services.provider_identity import upsert_player_provider_mapping
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points


LEGEND_BEY_NAME = "Legend Bey"
LEGEND_BEY_SCHOOL = "Ohio State"
LEGEND_BEY_POSITION = "RB"
LEGEND_BEY_ESPN_ID = "5182122"
OHIO_STATE_WEEK_ONE_EVENT_ID = "401858432"
OHIO_STATE_ESPN_TEAM_ID = "194"
OBSOLETE_RB3_NAME = "Ja'Kobi Jackson"
CORRECTION_SOURCE = "editorial_depth_chart_correction"
CORRECTION_MARKER = "legend-bey-ohio-state-week1"
ESPN_PROFILE_URL = "https://www.espn.com/college-football/player/_/id/5182122/legend-bey"

# A conservative manual role baseline, retained only until the normal
# post-final outlook pipeline has enough verified game data to supersede it.
LEGEND_BEY_SEASON_PROJECTION = {
    "rush_yards": 360.0,
    "rush_tds": 4.0,
    "receptions": 20.0,
    "rec_yards": 270.0,
    "rec_tds": 3.0,
}


def _identity(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _one_bey(db: Session) -> Player:
    matches = db.scalars(
        select(Player).where(
            Player.name == LEGEND_BEY_NAME,
            Player.school == LEGEND_BEY_SCHOOL,
            Player.position == LEGEND_BEY_POSITION,
        )
    ).all()
    if len(matches) > 1:
        raise ValueError("Ambiguous Ohio State RB records for Legend Bey.")
    if matches:
        return matches[0]
    player = Player(name=LEGEND_BEY_NAME, school=LEGEND_BEY_SCHOOL, position=LEGEND_BEY_POSITION)
    db.add(player)
    db.flush()
    return player


def _obsolete_jackson(db: Session) -> Player | None:
    matches = [
        player
        for player in db.scalars(
            select(Player).where(Player.school == LEGEND_BEY_SCHOOL, Player.position == LEGEND_BEY_POSITION)
        ).all()
        if _identity(player.name) == _identity(OBSOLETE_RB3_NAME)
    ]
    if len(matches) > 1:
        raise ValueError("Ambiguous Ohio State Ja'Kobi Jackson records; refusing deletion.")
    return matches[0] if matches else None


def _profile_is_exact_bey(profile: dict[str, Any]) -> bool:
    athlete = profile.get("athlete") if isinstance(profile, dict) else None
    if not isinstance(athlete, dict):
        return False
    team = athlete.get("team") if isinstance(athlete.get("team"), dict) else {}
    position = athlete.get("position") if isinstance(athlete.get("position"), dict) else {}
    return (
        str(athlete.get("id") or "") == LEGEND_BEY_ESPN_ID
        and _identity(athlete.get("displayName") or athlete.get("name")) == _identity(LEGEND_BEY_NAME)
        and _identity(position.get("abbreviation") or position.get("displayName")) == "rb"
        and any(
            _identity(team.get(key)) in {"ohiostate", "ohiostatebuckeyes"}
            for key in ("location", "displayName", "shortDisplayName", "name")
        )
    )


def _final_summary_for_event(summary: dict[str, Any]) -> bool:
    header = summary.get("header") if isinstance(summary, dict) else None
    if not isinstance(header, dict) or str(header.get("id") or "") != OHIO_STATE_WEEK_ONE_EVENT_ID:
        return False
    competitions = header.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return False
    status = competitions[0].get("status") if isinstance(competitions[0], dict) else None
    status_type = status.get("type") if isinstance(status, dict) and isinstance(status.get("type"), dict) else {}
    return bool(status_type.get("completed")) or str(status_type.get("name") or "").upper() == "STATUS_FINAL"


def _bey_week_one_stats(summary: dict[str, Any]) -> dict[str, Any]:
    matches = [
        row
        for row in extract_player_box_score_stats(summary)
        if str(row.get("ESPNPlayerID") or "") == LEGEND_BEY_ESPN_ID
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one Legend Bey row in Ohio State's Week 1 ESPN box score.")
    stats = dict(matches[0])
    if (
        _identity(stats.get("PlayerName")) != _identity(LEGEND_BEY_NAME)
        or _identity(stats.get("School")) not in {"ohiostate", "ohiostatebuckeyes"}
        or str(stats.get("EventID") or "") != OHIO_STATE_WEEK_ONE_EVENT_ID
    ):
        raise ValueError("Legend Bey's ESPN box-score identity did not match Ohio State Week 1.")
    expected = {
        "rushing_attempts": 6.0,
        "rush_yards": 37.0,
        "rush_tds": 0.0,
        "receptions": 2.0,
        "rec_yards": 37.0,
        "rec_tds": 1.0,
    }
    for key, value in expected.items():
        if float(stats.get(key) or 0.0) != value:
            raise ValueError(f"Unexpected Legend Bey Week 1 {key}: {stats.get(key)!r}.")
    return stats


def _upsert_role_snapshot(
    db: Session,
    *,
    player: Player,
    season: int,
    week: int,
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
            school=LEGEND_BEY_SCHOOL,
            position=LEGEND_BEY_POSITION,
        )
        db.add(snapshot)
    snapshot.source = CORRECTION_SOURCE
    snapshot.school = LEGEND_BEY_SCHOOL
    snapshot.position = LEGEND_BEY_POSITION
    snapshot.depth_order = 3
    snapshot.role_status = "rotation"


def _protected_references(db: Session, *, player_id: int) -> dict[str, int]:
    """References that must never be removed merely to replace source data."""
    checks = {
        "roster_entries": select(func.count()).select_from(RosterEntry).where(RosterEntry.player_id == player_id),
        "draft_picks": select(func.count()).select_from(DraftPick).where(DraftPick.player_id == player_id),
        "mock_draft_picks": select(func.count()).select_from(MockDraftPick).where(MockDraftPick.player_id == player_id),
        "waiver_claims": select(func.count()).select_from(WaiverClaim).where(
            or_(WaiverClaim.add_player_id == player_id, WaiverClaim.drop_player_id == player_id)
        ),
        "league_player_events": select(func.count()).select_from(LeaguePlayerEvent).where(LeaguePlayerEvent.player_id == player_id),
        "saturday_pick_players": select(func.count()).select_from(SaturdayPickPlayer).where(SaturdayPickPlayer.player_id == player_id),
    }
    return {name: int(db.scalar(statement) or 0) for name, statement in checks.items()}


def apply_legend_bey_ohio_state_correction(
    db: Session,
    *,
    season: int,
    role_weeks: Iterable[int],
    profile: dict[str, Any],
    week_one_summary: dict[str, Any],
) -> dict[str, Any]:
    """Replace the obsolete source-only Ohio State RB3 with Legend Bey.

    The caller owns the transaction.  The write is idempotent and refuses to
    make changes unless ESPN confirms both the exact player identity and a
    final Week 1 stat line.
    """

    if not _profile_is_exact_bey(profile):
        raise ValueError("ESPN profile is not the exact Legend Bey / Ohio State / RB identity.")
    if not _final_summary_for_event(week_one_summary):
        raise ValueError("Ohio State Week 1 ESPN event is not an accepted final summary.")
    stats = _bey_week_one_stats(week_one_summary)
    game = db.scalar(
        select(Game).where(
            Game.external_id == OHIO_STATE_WEEK_ONE_EVENT_ID,
            Game.season == season,
            Game.week == 1,
        )
    )
    if game is None:
        raise ValueError("Ohio State's Week 1 game is missing from the canonical schedule.")

    obsolete = _obsolete_jackson(db)
    removed_obsolete = None
    if obsolete is not None:
        references = _protected_references(db, player_id=obsolete.id)
        active_references = {name: count for name, count in references.items() if count}
        if active_references:
            raise ValueError(
                "Refusing to delete Ja'Kobi Jackson because historical league data exists: "
                f"{active_references}."
            )
        removed_obsolete = obsolete.name
        db.delete(obsolete)
        db.flush()

    bey = _one_bey(db)
    projection_stats = {
        **LEGEND_BEY_SEASON_PROJECTION,
        "fpts": calculate_fantasy_points(LEGEND_BEY_SEASON_PROJECTION, position="RB"),
        "projection_season": season,
        "scoring_policy_version": "manual_correction_week1_role_baseline_v1",
        "source_fantasy_proj": None,
    }
    bey.sheet_projected_season_points = float(projection_stats["fpts"])
    bey.sheet_projection_stats = projection_stats
    bey.sheet_source_sheet_id = f"{CANONICAL_CORRECTION_SOURCE_PREFIX}{season}:{CORRECTION_MARKER}"
    bey.sheet_synced_at = datetime.now(timezone.utc)
    bey.depth_chart_position, bey.depth_order = "RB3", 3
    bey.player_class = "Freshman"
    bey.external_id = f"espn:{LEGEND_BEY_ESPN_ID}"
    bey.espn_source_url = ESPN_PROFILE_URL
    persist_espn_player_profile(bey, profile)
    upsert_player_provider_mapping(
        db,
        player_id=bey.id,
        provider="espn",
        provider_player_id=LEGEND_BEY_ESPN_ID,
        provider_team_id=OHIO_STATE_ESPN_TEAM_ID,
        match_confidence=1.0,
        verification_status="verified",
        reason="Exact ESPN Ohio State roster/profile and completed Week 1 box-score match for Legend Bey.",
    )

    effective_weeks = sorted({int(week) for week in role_weeks if 1 <= int(week) <= 13})
    if not effective_weeks:
        raise ValueError("Ohio State RB correction requires at least one regular-season week.")
    for week in effective_weeks:
        _upsert_role_snapshot(db, player=bey, season=season, week=week)

    normalized = [{"player_id": bey.id, "stats": stats}]
    persist_normalized_espn_player_stats(db, season=season, week=1, normalized_rows=normalized)
    db.flush()
    weekly = db.scalar(
        select(PlayerStat).where(
            PlayerStat.player_id == bey.id,
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
        "player_id": bey.id,
        "player": bey.name,
        "espn_player_id": LEGEND_BEY_ESPN_ID,
        "event_id": OHIO_STATE_WEEK_ONE_EVENT_ID,
        "week_one_fantasy_points": calculate_fantasy_points(stats, position="RB"),
        "season_projection": bey.sheet_projected_season_points,
        "depth_slot": bey.depth_chart_position,
        "deleted_obsolete_player": removed_obsolete,
        "role_weeks": effective_weeks,
    }
