"""Pure fixed-bracket topology for the canonical league postseason.

This module deliberately contains no ORM calls.  It gives the service stable
node keys and routes so bracket behavior can be exhaustively tested without a
database or provider fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SUPPORTED_PLAYOFF_TEAM_COUNTS = frozenset({2, 4, 6, 8})
HIGHER_SEED_TIEBREAKER = "HIGHER_SEED_V1"
FIXED_BRACKET_FORMAT_VERSION = "FIXED_BRACKET_V1"

SourceKind = Literal["seed", "winner", "loser"]


@dataclass(frozen=True)
class ParticipantSource:
    kind: SourceKind
    value: int | str


@dataclass(frozen=True)
class TopologyNode:
    key: str
    round_number: int
    matchup_type: str
    bracket_path: str
    slot_number: int
    team_a: ParticipantSource
    team_b: ParticipantSource


def seed(seed_number: int) -> ParticipantSource:
    return ParticipantSource("seed", seed_number)


def winner(node_key: str) -> ParticipantSource:
    return ParticipantSource("winner", node_key)


def loser(node_key: str) -> ParticipantSource:
    return ParticipantSource("loser", node_key)


def required_rounds(playoff_teams: int) -> int:
    if playoff_teams not in SUPPORTED_PLAYOFF_TEAM_COUNTS:
        raise ValueError("playoff team count must be one of 2, 4, 6, or 8")
    return {2: 1, 4: 2, 6: 3, 8: 3}[playoff_teams]


def build_bracket_topology(playoff_teams: int) -> tuple[TopologyNode, ...]:
    """Return all fixed bracket and placement nodes for a supported format."""
    if playoff_teams not in SUPPORTED_PLAYOFF_TEAM_COUNTS:
        raise ValueError("playoff team count must be one of 2, 4, 6, or 8")

    if playoff_teams == 2:
        return (
            TopologyNode("championship", 1, "CHAMPIONSHIP", "CHAMPIONSHIP", 1, seed(1), seed(2)),
        )

    if playoff_teams == 4:
        return (
            TopologyNode("semi_a", 1, "SEMIFINAL", "CHAMPIONSHIP", 1, seed(1), seed(4)),
            TopologyNode("semi_b", 1, "SEMIFINAL", "CHAMPIONSHIP", 2, seed(2), seed(3)),
            TopologyNode("championship", 2, "CHAMPIONSHIP", "CHAMPIONSHIP", 1, winner("semi_a"), winner("semi_b")),
            TopologyNode("third_place", 2, "THIRD_PLACE", "PLACEMENT", 2, loser("semi_a"), loser("semi_b")),
        )

    if playoff_teams == 6:
        return (
            TopologyNode("qf_a", 1, "QUARTERFINAL", "CHAMPIONSHIP", 1, seed(3), seed(6)),
            TopologyNode("qf_b", 1, "QUARTERFINAL", "CHAMPIONSHIP", 2, seed(4), seed(5)),
            TopologyNode("semi_a", 2, "SEMIFINAL", "CHAMPIONSHIP", 1, seed(1), winner("qf_b")),
            TopologyNode("semi_b", 2, "SEMIFINAL", "CHAMPIONSHIP", 2, seed(2), winner("qf_a")),
            TopologyNode("fifth_place", 2, "FIFTH_PLACE", "PLACEMENT", 3, loser("qf_a"), loser("qf_b")),
            TopologyNode("championship", 3, "CHAMPIONSHIP", "CHAMPIONSHIP", 1, winner("semi_a"), winner("semi_b")),
            TopologyNode("third_place", 3, "THIRD_PLACE", "PLACEMENT", 2, loser("semi_a"), loser("semi_b")),
        )

    return (
        TopologyNode("qf_a", 1, "QUARTERFINAL", "CHAMPIONSHIP", 1, seed(1), seed(8)),
        TopologyNode("qf_b", 1, "QUARTERFINAL", "CHAMPIONSHIP", 2, seed(4), seed(5)),
        TopologyNode("qf_c", 1, "QUARTERFINAL", "CHAMPIONSHIP", 3, seed(2), seed(7)),
        TopologyNode("qf_d", 1, "QUARTERFINAL", "CHAMPIONSHIP", 4, seed(3), seed(6)),
        TopologyNode("semi_a", 2, "SEMIFINAL", "CHAMPIONSHIP", 1, winner("qf_a"), winner("qf_b")),
        TopologyNode("semi_b", 2, "SEMIFINAL", "CHAMPIONSHIP", 2, winner("qf_c"), winner("qf_d")),
        TopologyNode("placement_semi_a", 2, "PLACEMENT_SEMIFINAL", "PLACEMENT", 3, loser("qf_a"), loser("qf_b")),
        TopologyNode("placement_semi_b", 2, "PLACEMENT_SEMIFINAL", "PLACEMENT", 4, loser("qf_c"), loser("qf_d")),
        TopologyNode("championship", 3, "CHAMPIONSHIP", "CHAMPIONSHIP", 1, winner("semi_a"), winner("semi_b")),
        TopologyNode("third_place", 3, "THIRD_PLACE", "PLACEMENT", 2, loser("semi_a"), loser("semi_b")),
        TopologyNode("fifth_place", 3, "FIFTH_PLACE", "PLACEMENT", 3, winner("placement_semi_a"), winner("placement_semi_b")),
        TopologyNode("seventh_place", 3, "SEVENTH_PLACE", "PLACEMENT", 4, loser("placement_semi_a"), loser("placement_semi_b")),
    )


def format_summary(playoff_teams: int) -> str:
    if playoff_teams == 2:
        return "Seeds 1–2 play for the championship."
    if playoff_teams == 4:
        return "Semifinal winners play for the championship; semifinal losers play for third place."
    if playoff_teams == 6:
        return "Seeds 1–2 receive first-round byes; seeds 3–6 play quarterfinals, then semifinals and placement games."
    if playoff_teams == 8:
        return "Quarterfinal, semifinal, championship, and full fifth-through-eighth placement paths."
    raise ValueError("playoff team count must be one of 2, 4, 6, or 8")
