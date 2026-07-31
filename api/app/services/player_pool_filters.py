from sqlalchemy import and_, func, or_

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.power4 import (
    CANONICAL_POWER4_TEAMS,
    SCHOOL_ALIASES,
    is_power4_school,
    normalize_school,
)


def generated_test_player_filter():
    name = func.lower(func.trim(Player.name))
    school = func.lower(func.trim(Player.school))
    return ~or_(
        and_(name.like("smoke player %"), school.like("smoke school %")),
        and_(name.like("smoke raw player %"), school.like("smoke raw school %")),
    )


# Notre Dame is an intentional fantasy-pool exception: it is independent, but
# included in the approved player-ID spreadsheet alongside the Power 4 teams.
_APPROVED_SCHOOLS = {
    *[school for schools in CANONICAL_POWER4_TEAMS.values() for school in schools],
    *SCHOOL_ALIASES.keys(),
    "Notre Dame",
}
_APPROVED_SCHOOL_KEYS = tuple(sorted(school.strip().lower() for school in _APPROVED_SCHOOLS))
ELIGIBLE_FANTASY_POSITIONS = ("QB", "RB", "WR", "TE", "K")
CANONICAL_PRESEASON_SOURCE_PREFIX = "canonical-preseason:"


def approved_school_player_filter():
    """SQL predicate for the canonical Power 4 + Notre Dame player universe."""
    return func.lower(func.trim(Player.school)).in_(_APPROVED_SCHOOL_KEYS)


def canonical_preseason_player_filter(season: int):
    """Restrict a query to the reviewed immutable player snapshot for a season.

    Provider syncs and historical imports may create or retain ``Player`` rows
    for statistics and identity resolution.  They must never silently become
    draftable or claimable.  The release bootstrap marks only rows reconciled
    against the versioned identity + projection snapshots with this prefix.
    """

    return Player.sheet_source_sheet_id.like(
        f"{CANONICAL_PRESEASON_SOURCE_PREFIX}{int(season)}:%"
    )


def canonical_fantasy_player_filter(season: int):
    """SQL predicate for the complete public-beta draft and waiver universe."""

    return and_(
        generated_test_player_filter(),
        approved_school_player_filter(),
        canonical_preseason_player_filter(season),
        Player.position.in_(ELIGIBLE_FANTASY_POSITIONS),
        Player.sheet_projected_season_points.isnot(None),
        Player.sheet_projected_season_points > 0,
    )


def is_approved_fantasy_school(school: str | None) -> bool:
    return bool(school) and (
        is_power4_school(school) or normalize_school(school) == normalize_school("Notre Dame")
    )


def is_canonical_fantasy_player(player: Player, season: int) -> bool:
    """Python equivalent of :func:`canonical_fantasy_player_filter`.

    Write paths load a player by primary key, so they need an equivalent
    instance-level guard rather than a query predicate.  Keeping this here
    prevents manual picks and claims from drifting from the displayed pool.
    """

    source_marker = (player.sheet_source_sheet_id or "").strip()
    try:
        projected_points = float(player.sheet_projected_season_points)
    except (TypeError, ValueError):
        projected_points = 0.0
    return bool(
        source_marker.startswith(f"{CANONICAL_PRESEASON_SOURCE_PREFIX}{int(season)}:")
        and is_approved_fantasy_school(player.school)
        and (player.position or "").strip().upper() in ELIGIBLE_FANTASY_POSITIONS
        and projected_points > 0
    )
