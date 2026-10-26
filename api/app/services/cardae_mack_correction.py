"""Owner-reviewed ASU RB order, exact provider identity, and verified history."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.integrations.espn import extract_player_box_score_stats
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.espn_player_lookup import persist_espn_player_profile
from collegefootballfantasy_api.app.services.espn_stats_sync import persist_final_espn_player_game_stats, persist_normalized_espn_player_stats
from collegefootballfantasy_api.app.services.official_role_corrections import publish_role_corrected_week, upsert_role_snapshot
from collegefootballfantasy_api.app.services.player_pool_filters import CANONICAL_CORRECTION_SOURCE_PREFIX, LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX
from collegefootballfantasy_api.app.services.provider_identity import upsert_player_provider_mapping

MACK_ESPN_ID = "5209382"
ASU_ESPN_ID = "9"
SOURCE = "owner_reviewed_depth_chart"
MARKER = "cardae-mack-asu-rb2-2026-10-26"
BIO_URL = "https://thesundevils.com/sports/football/roster/player/cardae-mack"


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _player(db: Session, name: str, *, create: bool = False) -> Player:
    matches = db.scalars(select(Player).where(Player.name == name, Player.school == "Arizona State", Player.position == "RB")).all()
    if len(matches) > 1 or (not matches and not create):
        raise ValueError(f"Expected one exact Arizona State RB: {name}.")
    if matches:
        return matches[0]
    player = Player(name=name, school="Arizona State", position="RB")
    db.add(player)
    db.flush()
    return player


def apply_cardae_mack_correction(
    db: Session, *, season: int, effective_week: int, profile: dict,
    summaries: list[dict], role_baselines: dict[int, dict],
) -> dict:
    """Caller owns the transaction; no deletion or other player's stats rewrite."""
    if season != 2026 or not 1 <= effective_week <= 13:
        raise ValueError("This reviewed correction is bounded to the 2026 regular season.")
    athlete = profile.get("athlete") or {}
    if not (
        str(athlete.get("id")) == MACK_ESPN_ID
        and _key(athlete.get("displayName")) == "cardaemack"
        and str((athlete.get("team") or {}).get("id")) == ASU_ESPN_ID
        and (athlete.get("position") or {}).get("abbreviation") == "RB"
    ):
        raise ValueError("Profile must verify Cardae Mack / Arizona State / RB / ESPN 5209382.")
    # Validate every provider game before writing any catalog changes.
    verified_games = []
    seen = set()
    for summary in summaries:
        header = summary.get("header") or {}
        event_id = str(header.get("id") or "")
        if event_id in seen:
            raise ValueError("Duplicate ASU game summary.")
        seen.add(event_id)
        game = db.scalar(select(Game).where(Game.external_id == event_id, Game.season == season))
        competitions = header.get("competitions") or []
        status = ((competitions[0].get("status") or {}).get("type") or {}) if competitions else {}
        if (game is None or game.week > effective_week or game.schedule_status not in {"final", "post"}
            or "Arizona State" not in {game.home_team, game.away_team}
            or not status.get("completed")):
            raise ValueError(f"ASU game {event_id} is not an accepted completed game.")
        rows = [r for r in extract_player_box_score_stats(summary) if str(r.get("ESPNPlayerID")) == MACK_ESPN_ID]
        if len(rows) > 1:
            raise ValueError("Ambiguous Mack box score.")
        if rows:
            row = rows[0]
            if _key(row.get("PlayerName")) != "cardaemack" or _key(row.get("School")) != "arizonastate":
                raise ValueError("Mack box-score identity mismatch.")
            verified_games.append((game, row))
    if not any(g.week == effective_week for g, _ in verified_games):
        raise ValueError("The latest completed week must include Mack's verified box score.")

    kyson = _player(db, "Kyson Brown")
    robinson = _player(db, "Demarius Robinson")
    jason = _player(db, "Jason Brown Jr.")
    mack = _player(db, "Cardae Mack", create=True)
    now = datetime.now(timezone.utc)
    # Reuse immutable reviewed slot baselines on every run, never another
    # player's actual results, rating, or a previously shifted baseline.
    for player, depth in ((mack, 2), (robinson, 3)):
        baseline = deepcopy(role_baselines[depth])
        baseline.update({"baseline_source": SOURCE, "source_fantasy_proj": None, "correction": MARKER})
        player.sheet_projection_stats = baseline
        player.sheet_projected_season_points = float(baseline["fpts"])
    mack.sheet_source_sheet_id = f"{CANONICAL_CORRECTION_SOURCE_PREFIX}{season}:{MARKER}"
    mack.sheet_synced_at = now
    mack.external_id = f"espn:{MACK_ESPN_ID}"
    persist_espn_player_profile(mack, profile)
    mack.player_class = "Freshman"
    mack.espn_height, mack.espn_height_inches = "5' 10\"", 70
    mack.espn_weight, mack.espn_jersey = "215 lbs", "25"
    mack.espn_hometown = "Houston, Texas"
    mack.espn_source_url = f"https://www.espn.com/college-football/player/_/id/{MACK_ESPN_ID}/cardae-mack"
    mack.bio_source, mack.bio_imported_at = "official_asu_espn_review", now
    upsert_player_provider_mapping(db, player_id=mack.id, provider="espn", provider_player_id=MACK_ESPN_ID,
        provider_team_id=ASU_ESPN_ID, match_confidence=1.0, verification_status="verified",
        reason=f"Exact ASU official roster and ESPN profile/roster/box-score identity. {BIO_URL}")
    for player, depth in ((kyson, 1), (mack, 2), (robinson, 3)):
        player.depth_chart_position, player.depth_order = f"RB{depth}", depth
        for week in range(effective_week, 14):
            upsert_role_snapshot(db, player=player, season=season, week=week, depth_order=depth,
                role_status="starter" if depth == 1 else "rotation", source=SOURCE)
    jason.depth_chart_position, jason.depth_order = None, None
    old_marker = jason.sheet_source_sheet_id or "previously-unmarked"
    if not old_marker.startswith(LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX):
        jason.sheet_source_sheet_id = f"{LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX}{season}:{MARKER}:{old_marker}"
    imported = []
    for game, stats in verified_games:
        rows = [{"player_id": mack.id, "stats": stats}]
        persist_normalized_espn_player_stats(db, season=season, week=game.week, normalized_rows=rows)
        db.flush()
        row = db.scalar(select(PlayerStat).where(PlayerStat.player_id == mack.id, PlayerStat.season == season, PlayerStat.week == game.week))
        row.source, row.verified = "espn_final_boxscore", True
        persist_final_espn_player_game_stats(db, season=season, week=game.week, game_id=game.id, normalized_rows=rows)
        imported.append(game.week)
    db.flush()
    projection_weeks = []
    for week in range(effective_week + 1, 14):
        baseline = db.scalar(current_published_projections_query(season=season, week=week, player_ids=(robinson.id,)))
        if baseline is not None:
            publish_role_corrected_week(db, players=[mack, robinson], season=season, week=week,
                source_url=BIO_URL, new_player_ids=frozenset({mack.id}), source_label=SOURCE)
            projection_weeks.append(week)
    db.flush()
    projections = db.scalars(select(WeeklyProjection).where(WeeklyProjection.player_id.in_((mack.id, robinson.id)),
        WeeklyProjection.season == season, WeeklyProjection.week.in_(projection_weeks),
        WeeklyProjection.projection_version == "CORRECTED_ROLE")).all()
    return {"player_id": mack.id, "active_depth": [{"id": p.id, "name": p.name, "slot": p.depth_chart_position} for p in (kyson, mack, robinson)],
        "removed_from_active_pool": {"id": jason.id, "name": jason.name},
        "verified_stat_weeks": imported, "future_projection_weeks": projection_weeks,
        "future_projections": [{"player_id": p.player_id, "week": p.week, "points": p.fantasy_points} for p in projections],
        "bio_source": BIO_URL, "espn_id": MACK_ESPN_ID}
