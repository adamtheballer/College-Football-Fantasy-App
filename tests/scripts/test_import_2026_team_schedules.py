from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "import_2026_team_schedules.py"


def load_module():
    spec = importlib.util.spec_from_file_location("import_2026_team_schedules", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schedule_stage_refuses_live_urls(tmp_path):
    module = load_module()

    with pytest.raises(ValueError, match="approved local CSV snapshot"):
        module.load_source(Path("https://docs.google.com/schedule.csv"))

    source = tmp_path / "schedule.csv"
    source.write_text("Season,Team\n2026,Texas\n", encoding="utf-8")
    assert module.load_source(source) == "Season,Team\n2026,Texas\n"
