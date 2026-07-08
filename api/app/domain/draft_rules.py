from __future__ import annotations

from collegefootballfantasy_api.app.models.team import Team

DRAFT_ACTIVE_STATUSES = {"scheduled", "live", "active"}
DRAFT_TERMINAL_STATUSES = {"completed", "cancelled", "reset"}


def draft_pick_team_for_number(teams: list[Team], pick_number: int) -> tuple[int, int, Team | None]:
    if pick_number < 1:
        raise ValueError("pick_number must be positive")
    if not teams:
        return 1, 1, None
    total_teams = len(teams)
    round_number = ((pick_number - 1) // total_teams) + 1
    round_pick = ((pick_number - 1) % total_teams) + 1
    ordered_teams = teams if round_number % 2 == 1 else list(reversed(teams))
    return round_number, round_pick, ordered_teams[round_pick - 1]


def snake_pick_for_number(pick_number: int, league_size: int) -> tuple[int, int, int]:
    if pick_number < 1:
        raise ValueError("pick_number must be positive")
    if league_size < 1:
        raise ValueError("league_size must be positive")
    round_number = ((pick_number - 1) // league_size) + 1
    slot_index = (pick_number - 1) % league_size
    round_pick = slot_index + 1 if round_number % 2 == 1 else league_size - slot_index
    return round_number, round_pick, round_pick


def total_draft_picks(roster_slots: dict[str, int], team_count: int) -> int:
    return sum(int(value) for value in roster_slots.values()) * team_count
