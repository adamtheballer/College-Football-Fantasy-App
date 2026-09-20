from sqlalchemy import and_, func, or_

from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.power4 import (
    CANONICAL_POWER4_TEAMS,
    PLAYOFF_ELIGIBLE_INDEPENDENTS,
    SCHOOL_ALIASES,
    is_power4_school,
    normalize_school,
    resolve_power4_school,
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
LEAGUE_CONFERENCE_CODES = ("SEC", "BIG10", "BIG12", "ACC", "INDEPENDENT")
DEFAULT_LEAGUE_CONFERENCE_CODES = LEAGUE_CONFERENCE_CODES
_CONFERENCE_CODE_ALIASES = {
    "BIG TEN": "BIG10",
    "BIGTEN": "BIG10",
    "B1G": "BIG10",
    "BIG 12": "BIG12",
    "INDEPENDENTS": "INDEPENDENT",
    "NOTRE DAME": "INDEPENDENT",
}
CANONICAL_PRESEASON_SOURCE_PREFIX = "canonical-preseason:"
CANONICAL_CORRECTION_SOURCE_PREFIX = "canonical-correction:"
LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX = "legacy-canonical-preseason:"


def approved_school_player_filter():
    """SQL predicate for the canonical Power 4 + Notre Dame player universe."""
    return func.lower(func.trim(Player.school)).in_(_APPROVED_SCHOOL_KEYS)


def normalize_league_conference_codes(values: list[str] | tuple[str, ...] | None) -> list[str]:
    """Return a stable, validated conference-pool selection for one league.

    ``None`` is deliberately the legacy-compatible full fantasy pool. An
    explicit empty selection is rejected so a commissioner cannot create a
    league with no legal draft or waiver players.
    """

    if values is None:
        return list(DEFAULT_LEAGUE_CONFERENCE_CODES)
    normalized: set[str] = set()
    for raw_value in values:
        value = str(raw_value).strip().upper()
        value = _CONFERENCE_CODE_ALIASES.get(value, value)
        if value not in LEAGUE_CONFERENCE_CODES:
            raise ValueError(f"unsupported conference: {raw_value}")
        normalized.add(value)
    if not normalized:
        raise ValueError("select at least one conference")
    return [code for code in LEAGUE_CONFERENCE_CODES if code in normalized]


def _schools_for_league_conference_codes(values: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    codes = set(normalize_league_conference_codes(values))
    schools: set[str] = {
        school
        for conference, conference_schools in CANONICAL_POWER4_TEAMS.items()
        if conference in codes
        for school in conference_schools
    }
    if "INDEPENDENT" in codes:
        schools.update(PLAYOFF_ELIGIBLE_INDEPENDENTS)
    # Player sources may use a supported alias. Include it only when its
    # canonical school belongs to the selected conference pool.
    schools.update(
        alias
        for alias, canonical in SCHOOL_ALIASES.items()
        if canonical in schools
    )
    return tuple(sorted(school.strip().lower() for school in schools))


def league_conference_player_filter(values: list[str] | tuple[str, ...] | None):
    """SQL predicate that confines a player query to a league's pool."""

    return func.lower(func.trim(Player.school)).in_(_schools_for_league_conference_codes(values))


def is_player_in_league_conference_scope(
    player: Player,
    values: list[str] | tuple[str, ...] | None,
) -> bool:
    """Instance-level equivalent used by draft and transaction write paths."""

    if not player.school:
        return False
    canonical_school = resolve_power4_school(player.school)
    if not canonical_school:
        return False
    allowed = set(normalize_league_conference_codes(values))
    if canonical_school in PLAYOFF_ELIGIBLE_INDEPENDENTS:
        return "INDEPENDENT" in allowed
    for conference, schools in CANONICAL_POWER4_TEAMS.items():
        if canonical_school in schools:
            return conference in allowed
    return False


def canonical_preseason_player_filter(season: int):
    """Restrict a query to reviewed players and explicit auditable corrections.

    Provider syncs and historical imports may create or retain ``Player`` rows
    for statistics and identity resolution. They must never silently become
    draftable or claimable. The release bootstrap marks approved source rows;
    a separately named correction marker is allowed only for an explicit,
    versioned production correction such as a player omitted from the original
    reviewed sheet. It is intentionally not a generic provider-import path.
    """

    return or_(
        Player.sheet_source_sheet_id.like(
            f"{CANONICAL_PRESEASON_SOURCE_PREFIX}{int(season)}:%"
        ),
        Player.sheet_source_sheet_id.like(
            f"{CANONICAL_CORRECTION_SOURCE_PREFIX}{int(season)}:%"
        ),
    )


def retired_canonical_preseason_player_filter(season: int):
    """Identify retained records removed from the reviewed current snapshot.

    A legacy marker preserves roster, trade, and historical-stat foreign keys,
    while making the record unavailable to every current-season surface.
    """

    return Player.sheet_source_sheet_id.like(
        f"{LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX}{int(season)}:%"
    )


def is_retired_canonical_preseason_player(player: Player, season: int) -> bool:
    return (player.sheet_source_sheet_id or "").strip().startswith(
        f"{LEGACY_CANONICAL_PRESEASON_SOURCE_PREFIX}{int(season)}:"
    )


def active_canonical_preseason_player_filter(season: int):
    """SQL predicate for the reviewed current player snapshot before ratings.

    This is the one active-player contract shared by the canonical bootstrap,
    CFB27 reconciliation, and draft/waiver eligibility.  Historical and
    legacy-preseason rows deliberately fail this predicate even when they are
    retained for foreign-key history.
    """

    return and_(
        generated_test_player_filter(),
        approved_school_player_filter(),
        canonical_preseason_player_filter(season),
        Player.position.in_(ELIGIBLE_FANTASY_POSITIONS),
        Player.sheet_projected_season_points.isnot(None),
        Player.sheet_projected_season_points > 0,
    )


def canonical_fantasy_player_filter(season: int):
    """SQL predicate for the complete public-beta draft and waiver universe."""

    return active_canonical_preseason_player_filter(season)


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
        (
            source_marker.startswith(f"{CANONICAL_PRESEASON_SOURCE_PREFIX}{int(season)}:")
            or source_marker.startswith(f"{CANONICAL_CORRECTION_SOURCE_PREFIX}{int(season)}:")
        )
        and is_approved_fantasy_school(player.school)
        and (player.position or "").strip().upper() in ELIGIBLE_FANTASY_POSITIONS
        and projected_points > 0
    )
