"""Normalization for the Google player-identity spreadsheet's bio fields."""

from __future__ import annotations


_PLAYER_CLASS_DISPLAY = {
    "FR": "Freshman",
    "FRESHMAN": "Freshman",
    "RS FR": "Redshirt Freshman",
    "REDSHIRT FRESHMAN": "Redshirt Freshman",
    "SO": "Sophomore",
    "SOPHOMORE": "Sophomore",
    "RS SO": "Redshirt Sophomore",
    "REDSHIRT SOPHOMORE": "Redshirt Sophomore",
    "JR": "Junior",
    "JUNIOR": "Junior",
    "RS JR": "Redshirt Junior",
    "REDSHIRT JUNIOR": "Redshirt Junior",
    "SR": "Senior",
    "SENIOR": "Senior",
    "RS SR": "Redshirt Senior",
    "REDSHIRT SENIOR": "Redshirt Senior",
    "GR": "Graduate",
    "GRAD": "Graduate",
    "GRADUATE": "Graduate",
    "GRADUATE STUDENT": "Graduate",
}


def normalize_sheet_player_class(value: str | None) -> str | None:
    """Return a player-card display class for a trusted sheet value.

    ``None`` signals an unsupported or blank source value so callers preserve
    the existing canonical value and include the row in their review report.
    """

    if not value:
        return None
    normalized = " ".join(
        str(value).strip().upper().replace("_", " ").replace("-", " ").replace(".", "").split()
    )
    return _PLAYER_CLASS_DISPLAY.get(normalized)

