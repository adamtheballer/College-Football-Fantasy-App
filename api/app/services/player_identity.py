from __future__ import annotations

import re

from api.app.models.player import Player


def normalize_player_position(value: str | None) -> str:
    normalized = (value or "").strip().upper()
    normalized = re.sub(r"[^A-Z0-9]+", "", normalized)
    normalized = re.sub(r"\d+$", "", normalized)
    aliases = {"PK": "K", "HB": "RB", "FB": "RB", "FL": "WR", "SE": "WR"}
    return aliases.get(normalized, normalized)


def normalize_player_identity_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def canonical_player_key(name: str | None, position: str | None, school: str | None) -> tuple[str, str, str]:
    return (
        normalize_player_identity_text(name),
        normalize_player_position(position),
        normalize_player_identity_text(school),
    )


def player_canonical_key(player: Player) -> tuple[str, str, str]:
    return canonical_player_key(player.name, player.position, player.school)


def player_has_sheet_board_data(player: Player) -> bool:
    return (
        player.sheet_adp is not None
        or player.sheet_projected_season_points is not None
        or player.sheet_source_sheet_id is not None
    )


def player_board_sort_tuple(player: Player) -> tuple[int, float, float, str, int]:
    has_sheet_data = 0 if player_has_sheet_board_data(player) else 1
    adp = float(player.sheet_adp) if player.sheet_adp is not None and player.sheet_adp > 0 else 9_999_999.0
    projection = -(float(player.sheet_projected_season_points) if player.sheet_projected_season_points is not None else 0.0)
    return (has_sheet_data, adp, projection, normalize_player_identity_text(player.name), player.id)


def prefer_canonical_player(current: Player, candidate: Player) -> Player:
    return candidate if player_board_sort_tuple(candidate) < player_board_sort_tuple(current) else current
