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


def approved_school_player_filter():
    """SQL predicate for the canonical Power 4 + Notre Dame player universe."""
    return func.lower(func.trim(Player.school)).in_(_APPROVED_SCHOOL_KEYS)


def is_approved_fantasy_school(school: str | None) -> bool:
    return bool(school) and (
        is_power4_school(school) or normalize_school(school) == normalize_school("Notre Dame")
    )
