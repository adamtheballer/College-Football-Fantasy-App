"""Deterministic, shadow-only league score projections.

The live scorer records immutable player-game calculations.  This service
projects those records through locked lineups without writing legacy public
``PlayerWeekScore``, ``TeamWeekScore``, ``Matchup``, or ``Standing`` rows.
It deliberately reports missing or ambiguous evidence instead of substituting
zeroes or selecting a score arbitrarily.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.domain.live_scoring_contract import (
    CORRECTED,
    DELAYED,
    FINAL_VERIFIED,
    FINAL_UNVERIFIED,
)
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.live_scoring import (
    PlayerGameStatRevision,
    ProviderRawEvent,
    ScoringCalculationSnapshot,
    ShadowScoringReadModel,
)
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
from collegefootballfantasy_api.app.services.live_projection_service import live_projected_points
from collegefootballfantasy_api.app.services.matchup_probability import calculate_matchup_win_probability
from collegefootballfantasy_api.app.services.live_scoring_service import canonical_json, sha256, utcnow


SHADOW_READ_MODEL_VERSION = "shadow_read_model_v2"


class ShadowReadModelError(ValueError):
    """A shadow projection cannot be built or stored safely."""


@dataclass(frozen=True)
class ShadowReadModelProjection:
    league_id: int
    season: int
    week: int
    source_sha256: str
    status: str
    payload: dict[str, Any]


def _lineup_status(*, missing: bool, ambiguous: bool, lifecycle_states: set[str]) -> str:
    if missing or ambiguous:
        return "unavailable"
    if DELAYED in lifecycle_states:
        return "delayed"
    if lifecycle_states and lifecycle_states.issubset({FINAL_VERIFIED, CORRECTED, "final"}):
        return "final"
    if FINAL_UNVERIFIED in lifecycle_states:
        return "provisional"
    return "provisional"


def _latest_shadow_scores(
    db: Session,
    *,
    league_id: int,
    season: int,
    week: int,
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    """Return one verified scoring lineage per player or an explicit blocker.

    A player may have many historical revisions, but only the highest immutable
    revision may contribute to this projection.  Multiple policy snapshots for
    the same revision are surfaced as an ambiguity; this service never chooses
    one based on insertion time.
    """
    rows = (
        db.query(ScoringCalculationSnapshot, PlayerGameStatRevision, ProviderRawEvent)
        .join(PlayerGameStatRevision, PlayerGameStatRevision.id == ScoringCalculationSnapshot.stat_revision_id)
        .join(ProviderRawEvent, ProviderRawEvent.id == PlayerGameStatRevision.raw_event_id)
        .filter(
            ScoringCalculationSnapshot.league_id == league_id,
            ScoringCalculationSnapshot.season == season,
            ScoringCalculationSnapshot.week == week,
            ScoringCalculationSnapshot.publish_state == "shadow",
            PlayerGameStatRevision.season == season,
            PlayerGameStatRevision.week == week,
            PlayerGameStatRevision.status == "accepted",
        )
        .order_by(
            PlayerGameStatRevision.player_id.asc(),
            PlayerGameStatRevision.game_id.asc(),
            PlayerGameStatRevision.revision_number.desc(),
            ScoringCalculationSnapshot.id.asc(),
        )
        .all()
    )

    by_player_game: dict[tuple[int, int], list[tuple[ScoringCalculationSnapshot, PlayerGameStatRevision, ProviderRawEvent]]] = {}
    for snapshot, revision, raw_event in rows:
        by_player_game.setdefault((revision.player_id, revision.game_id), []).append((snapshot, revision, raw_event))

    selected: dict[int, dict[str, Any]] = {}
    blockers: list[dict[str, Any]] = []
    conflicted_player_ids: set[int] = set()
    for (player_id, game_id), candidates in sorted(by_player_game.items()):
        if player_id in conflicted_player_ids:
            continue
        highest_revision = max(revision.revision_number for _snapshot, revision, _event in candidates)
        newest = [(snapshot, revision, event) for snapshot, revision, event in candidates if revision.revision_number == highest_revision]
        policy_hashes = {snapshot.scoring_policy_hash for snapshot, _revision, _event in newest}
        if len(policy_hashes) != 1:
            blockers.append(
                {
                    "kind": "ambiguous_policy_snapshot",
                    "player_id": player_id,
                    "game_id": game_id,
                    "revision_number": highest_revision,
                }
            )
            continue
        # Immutable snapshot IDs only break ties for duplicate evidence with the
        # same exact policy; the calculated points must still agree.
        scores = {snapshot.score for snapshot, _revision, _event in newest}
        if len(scores) != 1:
            blockers.append(
                {
                    "kind": "ambiguous_calculation_snapshot",
                    "player_id": player_id,
                    "game_id": game_id,
                    "revision_number": highest_revision,
                }
            )
            continue
        snapshot, revision, raw_event = newest[0]
        current = selected.get(player_id)
        if current is not None:
            blockers.append(
                {
                    "kind": "multiple_games_for_player_week",
                    "player_id": player_id,
                    "game_ids": sorted([current["game_id"], game_id]),
                }
            )
            selected.pop(player_id, None)
            conflicted_player_ids.add(player_id)
            continue
        selected[player_id] = {
            "game_id": game_id,
            "stat_revision_id": revision.id,
            "revision_number": revision.revision_number,
            "revision_source_sha256": revision.source_hash,
            "lifecycle_state": revision.lifecycle_state,
            "snapshot_id": snapshot.id,
            "score": snapshot.score,
            "scoring_policy_hash": snapshot.scoring_policy_hash,
            "scorer_version": snapshot.scorer_version,
            "provider_payload": raw_event.payload_json,
        }
    return selected, blockers


def build_shadow_read_model(
    db: Session,
    *,
    league_id: int,
    season: int,
    week: int,
) -> ShadowReadModelProjection:
    """Build a side-effect-free league projection from immutable evidence."""
    lineups = (
        db.query(LineupWeekSnapshot)
        .filter(
            LineupWeekSnapshot.league_id == league_id,
            LineupWeekSnapshot.season == season,
            LineupWeekSnapshot.week == week,
        )
        .order_by(
            LineupWeekSnapshot.team_id.asc(),
            LineupWeekSnapshot.is_starter.desc(),
            LineupWeekSnapshot.slot.asc(),
            LineupWeekSnapshot.player_id.asc(),
        )
        .all()
    )
    matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league_id, Matchup.season == season, Matchup.week == week)
        .order_by(Matchup.id.asc())
        .all()
    )
    scores_by_player, source_blockers = _latest_shadow_scores(
        db,
        league_id=league_id,
        season=season,
        week=week,
    )
    blocked_player_ids = {
        blocker["player_id"] for blocker in source_blockers if isinstance(blocker.get("player_id"), int)
    }
    player_ids = {lineup.player_id for lineup in lineups}
    published_projections = {
        row.player_id: row
        for row in db.scalars(
            current_published_projections_query(
                season=season,
                week=week,
                player_ids=player_ids,
            )
        ).all()
    }

    team_ids = {lineup.team_id for lineup in lineups}
    for matchup in matchups:
        team_ids.update({matchup.home_team_id, matchup.away_team_id})
    teams: dict[int, dict[str, Any]] = {
        team_id: {
            "team_id": team_id,
            "starter_points": 0.0,
            "bench_points": 0.0,
            "starter_live_projection": 0.0,
            "bench_live_projection": 0.0,
            "starter_pre_game_projection": 0.0,
            "lineup": [],
            "missing_player_ids": [],
            "lifecycle_states": set(),
            "ambiguous": False,
        }
        for team_id in sorted(team_ids)
    }

    source_lineage: list[dict[str, Any]] = []
    projection_lineage: list[dict[str, Any]] = []
    for lineup in lineups:
        team = teams[lineup.team_id]
        scoring = scores_by_player.get(lineup.player_id)
        projection = published_projections.get(lineup.player_id)
        pre_game_projection = float(projection.fantasy_points) if projection is not None else None
        if projection is not None:
            projection_lineage.append(
                {
                    "player_id": lineup.player_id,
                    "projection_id": projection.id,
                    "projection_version": projection.projection_version,
                    "fantasy_points": pre_game_projection,
                    "updated_at": projection.updated_at.isoformat(),
                }
            )
        unavailable = lineup.player_id in blocked_player_ids or (scoring is None and pre_game_projection is None)
        actual_points = None if scoring is None else float(scoring["score"])
        live_projection, projection_source, game_progress = live_projected_points(
            pre_game_projection=pre_game_projection,
            actual_points=actual_points,
            lifecycle_state=None if scoring is None else scoring["lifecycle_state"],
            provider_payload=None if scoring is None else scoring["provider_payload"],
        )
        line: dict[str, Any] = {
            "player_id": lineup.player_id,
            "slot": lineup.slot,
            "is_starter": lineup.is_starter,
            "game_start_at": lineup.game_start_at.isoformat() if lineup.game_start_at else None,
            "locked_at": lineup.locked_at.isoformat() if lineup.locked_at else None,
            "score": None if unavailable else actual_points,
            "pre_game_projection_points": pre_game_projection,
            "live_projection_points": None if unavailable else round(live_projection, 2) if live_projection is not None else None,
            "projection_source": projection_source,
            "game_progress": round(game_progress, 4),
            "availability": "unavailable" if unavailable else "available",
        }
        if unavailable:
            team["missing_player_ids"].append(lineup.player_id)
            team["ambiguous"] = team["ambiguous"] or lineup.player_id in blocked_player_ids
        else:
            if scoring is not None:
                team["lifecycle_states"].add(scoring["lifecycle_state"])
            if lineup.is_starter:
                team["starter_points"] += actual_points or 0.0
                team["starter_pre_game_projection"] += pre_game_projection or 0.0
                team["starter_live_projection"] += live_projection or 0.0
            else:
                team["bench_points"] += actual_points or 0.0
                team["bench_live_projection"] += live_projection or 0.0
            line.update(
                {
                    "game_id": None if scoring is None else scoring["game_id"],
                    "stat_revision_id": None if scoring is None else scoring["stat_revision_id"],
                    "revision_number": None if scoring is None else scoring["revision_number"],
                    "lifecycle_state": None if scoring is None else scoring["lifecycle_state"],
                }
            )
            if scoring is not None:
                source_lineage.append({
                    "player_id": lineup.player_id,
                    "game_id": scoring["game_id"],
                    "stat_revision_id": scoring["stat_revision_id"],
                    "revision_source_sha256": scoring["revision_source_sha256"],
                    "snapshot_id": scoring["snapshot_id"],
                    "score": scoring["score"],
                    "scoring_policy_hash": scoring["scoring_policy_hash"],
                    "scorer_version": scoring["scorer_version"],
                    "pre_game_projection_points": pre_game_projection,
                })
        team["lineup"].append(line)

    team_payloads: list[dict[str, Any]] = []
    for team_id, team in sorted(teams.items()):
        missing = bool(team["missing_player_ids"]) or not team["lineup"]
        if not team["lineup"]:
            source_blockers.append({"kind": "missing_locked_lineup", "team_id": team_id})
        status = _lineup_status(
            missing=missing,
            ambiguous=team["ambiguous"],
            lifecycle_states=team["lifecycle_states"],
        )
        team_payloads.append(
            {
                "team_id": team_id,
                "starter_points": round(team["starter_points"], 2),
                "bench_points": round(team["bench_points"], 2),
                "starter_pre_game_projection": round(team["starter_pre_game_projection"], 2),
                "starter_live_projection": round(team["starter_live_projection"], 2),
                "bench_live_projection": round(team["bench_live_projection"], 2),
                "status": status,
                "missing_player_ids": sorted(team["missing_player_ids"]),
                "lineup": team["lineup"],
            }
        )

    teams_by_id = {team["team_id"]: team for team in team_payloads}
    matchup_payloads: list[dict[str, Any]] = []
    for matchup in matchups:
        home = teams_by_id[matchup.home_team_id]
        away = teams_by_id[matchup.away_team_id]
        statuses = {home["status"], away["status"]}
        status = "final" if statuses == {"final"} else "unavailable" if "unavailable" in statuses else "provisional"
        probability = None
        if "unavailable" not in statuses:
            calculated_probability = calculate_matchup_win_probability(
                home["starter_live_projection"], away["starter_live_projection"]
            )
            if calculated_probability is not None:
                probability = {
                    "home": calculated_probability[0],
                    "away": calculated_probability[1],
                }
        matchup_payloads.append(
            {
                "matchup_id": matchup.id,
                "home_team_id": matchup.home_team_id,
                "away_team_id": matchup.away_team_id,
                "home_starter_points": home["starter_points"],
                "away_starter_points": away["starter_points"],
                "home_live_projection": home["starter_live_projection"],
                "away_live_projection": away["starter_live_projection"],
                "win_probability": probability,
                "status": status,
            }
        )

    source = {
        "calculation_version": SHADOW_READ_MODEL_VERSION,
        "league_id": league_id,
        "season": season,
        "week": week,
        "lineups": [
            {
                "team_id": line.team_id,
                "player_id": line.player_id,
                "slot": line.slot,
                "is_starter": line.is_starter,
                "game_start_at": line.game_start_at.isoformat() if line.game_start_at else None,
                "locked_at": line.locked_at.isoformat() if line.locked_at else None,
            }
            for line in lineups
        ],
        "source_lineage": sorted(source_lineage, key=canonical_json),
        "published_projection_inputs": sorted(projection_lineage, key=canonical_json),
        "source_blockers": sorted(source_blockers, key=canonical_json),
        "matchups": [
            {"matchup_id": row.id, "home_team_id": row.home_team_id, "away_team_id": row.away_team_id}
            for row in matchups
        ],
    }
    source_sha256 = sha256(source)
    overall_status = "unavailable" if source_blockers or any(team["status"] == "unavailable" for team in team_payloads) else (
        "final" if team_payloads and all(team["status"] == "final" for team in team_payloads) else "provisional"
    )
    payload = {
        "calculation_version": SHADOW_READ_MODEL_VERSION,
        "league_id": league_id,
        "season": season,
        "week": week,
        "status": overall_status,
        "teams": team_payloads,
        "matchups": matchup_payloads,
        "blockers": sorted(source_blockers, key=canonical_json),
    }
    return ShadowReadModelProjection(
        league_id=league_id,
        season=season,
        week=week,
        source_sha256=source_sha256,
        status=overall_status,
        payload=payload,
    )


def persist_shadow_read_model(
    db: Session,
    projection: ShadowReadModelProjection,
) -> ShadowScoringReadModel:
    """Persist a projection only in explicit shadow mode, never public mode."""
    if settings.scoring_mode != "shadow":
        raise ShadowReadModelError("shadow read-model persistence requires SCORING_MODE=shadow")
    existing = (
        db.query(ShadowScoringReadModel)
        .filter(
            ShadowScoringReadModel.league_id == projection.league_id,
            ShadowScoringReadModel.season == projection.season,
            ShadowScoringReadModel.week == projection.week,
            ShadowScoringReadModel.source_sha256 == projection.source_sha256,
        )
        .one_or_none()
    )
    if existing:
        return existing
    row = ShadowScoringReadModel(
        league_id=projection.league_id,
        season=projection.season,
        week=projection.week,
        source_sha256=projection.source_sha256,
        calculation_version=SHADOW_READ_MODEL_VERSION,
        status=projection.status,
        payload_json=projection.payload,
        created_at=utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def latest_shadow_read_model(
    db: Session,
    *,
    league_id: int,
    season: int,
    week: int,
) -> ShadowScoringReadModel | None:
    """Return immutable shadow evidence without rebuilding or mutating it."""
    return (
        db.query(ShadowScoringReadModel)
        .filter(
            ShadowScoringReadModel.league_id == league_id,
            ShadowScoringReadModel.season == season,
            ShadowScoringReadModel.week == week,
        )
        .order_by(ShadowScoringReadModel.id.desc())
        .first()
    )
