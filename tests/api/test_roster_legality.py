import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from collegefootballfantasy_api.app.services.roster_legality import assign_best_roster_slot_for_position


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "roster_legality_cases.json"
ROSTER_LEGALITY_CASES = json.loads(FIXTURE_PATH.read_text())


@pytest.mark.parametrize("case", ROSTER_LEGALITY_CASES, ids=lambda case: case["name"])
def test_shared_roster_legality_cases(case):
    roster_entries = [SimpleNamespace(slot=entry["slot"]) for entry in case["roster"]]

    assert (
        assign_best_roster_slot_for_position(
            case["candidate_position"],
            roster_entries,
            case["roster_slots"],
        )
        == case["expected_slot"]
    )
