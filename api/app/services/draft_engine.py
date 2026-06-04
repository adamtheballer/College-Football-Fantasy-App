from collections.abc import Sequence
from typing import TypeVar


T = TypeVar("T")


def get_total_picks(team_count: int, roster_slots: dict | None) -> int:
    draftable_slots = {"QB", "RB", "WR", "TE", "FLEX", "SUPERFLEX", "K", "DEF", "BENCH"}
    rounds = 0
    for raw_slot, raw_count in (roster_slots or {}).items():
        slot = str(raw_slot).upper()
        if slot not in draftable_slots:
            continue
        try:
            rounds += max(0, int(raw_count))
        except (TypeError, ValueError):
            continue
    return max(0, int(team_count)) * max(0, rounds)


def get_round_number(overall_pick: int, team_count: int) -> int:
    if overall_pick <= 0 or team_count <= 0:
        return 0
    return ((overall_pick - 1) // team_count) + 1


def get_round_pick(overall_pick: int, team_count: int) -> int:
    if overall_pick <= 0 or team_count <= 0:
        return 0
    return ((overall_pick - 1) % team_count) + 1


def get_snake_team_for_pick(teams: Sequence[T], overall_pick: int) -> T | None:
    team_count = len(teams)
    if overall_pick <= 0 or team_count <= 0:
        return None
    round_number = get_round_number(overall_pick, team_count)
    zero_based_pick = get_round_pick(overall_pick, team_count) - 1
    index = zero_based_pick if round_number % 2 == 1 else team_count - 1 - zero_based_pick
    return teams[index]


def is_draft_complete(picks_made: int, total_picks: int) -> bool:
    return total_picks > 0 and picks_made >= total_picks


def calculate_total_picks(team_count: int, round_count: int) -> int:
    if team_count <= 0:
        raise ValueError("team_count must be positive")
    if round_count <= 0:
        raise ValueError("round_count must be positive")
    return int(team_count) * int(round_count)


def calculate_overall_pick(round_number: int, round_pick: int, team_count: int) -> int:
    if team_count <= 0:
        raise ValueError("team_count must be positive")
    if round_number <= 0:
        raise ValueError("round_number must be positive")
    if round_pick <= 0 or round_pick > team_count:
        raise ValueError("round_pick must be between 1 and team_count")
    return ((int(round_number) - 1) * int(team_count)) + int(round_pick)


def validate_pick_number(overall_pick: int, total_picks: int) -> int:
    if total_picks <= 0:
        raise ValueError("total_picks must be positive")
    if overall_pick <= 0 or overall_pick > total_picks:
        raise ValueError("overall_pick must be between 1 and total_picks")
    return int(overall_pick)


def get_snake_order_for_round(participants: Sequence[T], round_number: int) -> list[T]:
    if round_number <= 0:
        raise ValueError("round_number must be positive")
    ordered = list(participants)
    if round_number % 2 == 0:
        ordered.reverse()
    return ordered


def get_participant_for_pick(participants: Sequence[T], overall_pick: int) -> T | None:
    team_count = len(participants)
    if overall_pick <= 0 or team_count <= 0:
        return None
    round_number = get_round_number(overall_pick, team_count)
    round_pick = get_round_pick(overall_pick, team_count)
    round_order = get_snake_order_for_round(participants, round_number)
    return round_order[round_pick - 1]


def is_final_pick(overall_pick: int, total_picks: int) -> bool:
    return total_picks > 0 and overall_pick >= total_picks
