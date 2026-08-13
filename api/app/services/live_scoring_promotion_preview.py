"""Read-only finalization preview for the live-scoring promotion boundary.

The live scorer intentionally writes only append-only provider evidence and
shadow read models.  This module determines what a separately authorized
public promotion *would* write after a game week is fully certified.  It
never calls ``add``, ``flush`` or ``commit``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.domain.live_scoring_contract import CORRECTED, FINAL_VERIFIED
from collegefootballfantasy_api.app.models.live_scoring import PlayerGameStatRevision, ProviderGamePollState
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points, get_scoring_rules
from collegefootballfantasy_api.app.services.live_scoring_service import canonical_json, sha256


FINAL_CERTIFIED_STATES = frozenset({FINAL_VERIFIED, CORRECTED, "final"})
PROMOTION_PREVIEW_VERSION = "live_scoring_promotion_preview_v1"


@dataclass(frozen=True)
class PlayerPromotionPlan:
    player_id: int
    game_id: int
    player_name: str
    position: str
    revision_id: int
    revision_number: int
    fantasy_points: float
    player_stat_action: str
    player_game_stat_action: str


@dataclass(frozen=True)
class PromotionPreview:
    season: int
    week: int
    status: str
    database_writes: int
    source_sha256: str
    player_stat_plans: tuple[PlayerPromotionPlan, ...]
    blockers: tuple[dict[str, Any], ...]
    dependent_recalculations: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "preview_version": PROMOTION_PREVIEW_VERSION,
            "season": self.season,
            "week": self.week,
            "status": self.status,
            "database_writes": self.database_writes,
            "source_sha256": self.source_sha256,
            "player_stat_plans": [asdict(plan) for plan in self.player_stat_plans],
            "blockers": list(self.blockers),
            "dependent_recalculations": self.dependent_recalculations,
        }


def _record_action(existing: object | None, desired_stats: dict[str, Any], *, source: str) -> str:
    if existing is None:
        return "CREATE"
    if canonical_json(getattr(existing, "stats")) == canonical_json(desired_stats) and getattr(existing, "source") == source:
        if not isinstance(existing, PlayerStat) or bool(existing.verified):
            return "UNCHANGED"
    return "UPDATE"


def _week_revisions(db: Session, *, season: int, week: int) -> list[PlayerGameStatRevision]:
    """Return one newest immutable revision per player/game without guessing."""
    revisions = (
        db.query(PlayerGameStatRevision)
        .filter(PlayerGameStatRevision.season == season, PlayerGameStatRevision.week == week)
        .order_by(
            PlayerGameStatRevision.player_id.asc(),
            PlayerGameStatRevision.game_id.asc(),
            PlayerGameStatRevision.revision_number.desc(),
            PlayerGameStatRevision.id.asc(),
        )
        .all()
    )
    chosen: list[PlayerGameStatRevision] = []
    seen: set[tuple[int, int]] = set()
    for revision in revisions:
        key = (revision.player_id, revision.game_id)
        if key not in seen:
            seen.add(key)
            chosen.append(revision)
    return chosen


def build_final_scoring_promotion_preview(
    db: Session,
    *,
    season: int,
    week: int,
) -> PromotionPreview:
    """Plan a certified final-week promotion without mutating public data.

    One incomplete or uncertified source blocks the entire week.  The returned
    dependent actions are descriptors only: player history, next-week
    projections, values, standings, and matchup read models require a later
    explicit public-promotion authorization.
    """
    poll_states = {
        state.game_id: state
        for state in db.query(ProviderGamePollState)
        .filter(ProviderGamePollState.season == season, ProviderGamePollState.week == week)
        .all()
    }
    players = {player.id: player for player in db.query(Player).all()}
    existing_player_stats = {
        row.player_id: row
        for row in db.query(PlayerStat)
        .filter(PlayerStat.season == season, PlayerStat.week == week)
        .all()
    }
    existing_game_stats = {
        (row.player_id, row.game_id): row
        for row in db.query(PlayerGameStat)
        .filter(PlayerGameStat.season == season, PlayerGameStat.week == week)
        .all()
    }

    revisions = _week_revisions(db, season=season, week=week)
    blockers: list[dict[str, Any]] = []
    if not revisions:
        # An empty week is not a successful finalization.  Treating it as one
        # would permit a downstream promotion to mark a week complete without
        # any immutable provider evidence behind player histories or scores.
        blockers.append({"kind": "NO_FINAL_STAT_REVISIONS", "season": season, "week": week})
    seen_player_games: dict[int, int] = {}
    plans: list[PlayerPromotionPlan] = []
    rules = get_scoring_rules()
    for revision in revisions:
        player = players.get(revision.player_id)
        if player is None:
            blockers.append({"kind": "MISSING_CANONICAL_PLAYER", "player_id": revision.player_id, "game_id": revision.game_id})
            continue
        prior_game = seen_player_games.setdefault(player.id, revision.game_id)
        if prior_game != revision.game_id:
            blockers.append({"kind": "PLAYER_HAS_MULTIPLE_WEEK_GAMES", "player_id": player.id, "game_ids": sorted({prior_game, revision.game_id})})
            continue
        state = poll_states.get(revision.game_id)
        if state is None or state.lifecycle_state not in FINAL_CERTIFIED_STATES:
            blockers.append({
                "kind": "GAME_NOT_FINAL_CERTIFIED",
                "player_id": player.id,
                "game_id": revision.game_id,
                "lifecycle_state": state.lifecycle_state if state else None,
            })
            continue
        if revision.status != "accepted" or revision.completeness != "complete":
            blockers.append({
                "kind": "INCOMPLETE_FINAL_STAT_REVISION",
                "player_id": player.id,
                "game_id": revision.game_id,
                "revision_id": revision.id,
                "revision_status": revision.status,
                "completeness": revision.completeness,
            })
            continue

        final_stats = dict(revision.stats_json)
        final_stats["fantasy_points"] = calculate_fantasy_points(final_stats, rules, position=player.position)
        source = "espn_live_final_v1"
        plans.append(PlayerPromotionPlan(
            player_id=player.id,
            game_id=revision.game_id,
            player_name=player.name,
            position=player.position,
            revision_id=revision.id,
            revision_number=revision.revision_number,
            fantasy_points=float(final_stats["fantasy_points"]),
            player_stat_action=_record_action(existing_player_stats.get(player.id), final_stats, source=source),
            player_game_stat_action=_record_action(existing_game_stats.get((player.id, revision.game_id)), final_stats, source=source),
        ))

    plans.sort(key=lambda plan: (plan.player_id, plan.game_id))
    blockers.sort(key=lambda blocker: (str(blocker.get("kind")), int(blocker.get("player_id", -1))))
    source_sha256 = sha256({
        "preview_version": PROMOTION_PREVIEW_VERSION,
        "season": season,
        "week": week,
        "plans": [asdict(plan) for plan in plans],
        "blockers": blockers,
    })
    status = "blocked" if blockers else "ready_for_authorized_promotion"
    dependent_state = "blocked_by_finalization_preview" if blockers else "requires_authorized_public_promotion"
    return PromotionPreview(
        season=season,
        week=week,
        status=status,
        database_writes=0,
        source_sha256=source_sha256,
        player_stat_plans=tuple(plans),
        blockers=tuple(blockers),
        dependent_recalculations={
            "player_card_game_log_and_history": dependent_state,
            "season_positional_rank_snapshot": dependent_state,
            "next_week_projection_rebuild": dependent_state,
            "current_value_recalculation": dependent_state,
            "matchups_and_win_probability": dependent_state,
            "standings": dependent_state,
        },
    )
