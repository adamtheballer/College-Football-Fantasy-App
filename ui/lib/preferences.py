from __future__ import annotations

import json
from pathlib import Path

PREFS_PATH = Path(__file__).resolve().parents[1] / ".preferences.json"


def _default_preferences() -> dict:
    return {
        "theme": "ESPN",
        "favorite_team": "Alabama",
        "notifications": {
            "injury_alerts": True,
            "lineup_reminders": True,
            "trade_alerts": False,
        },
    }


def load_preferences() -> dict:
    if not PREFS_PATH.exists():
        return _default_preferences()
    try:
        with PREFS_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        defaults = _default_preferences()
        defaults.update(data)
        defaults["notifications"].update(data.get("notifications", {}))
        return defaults
    except Exception:
        return _default_preferences()


def save_preferences(prefs: dict) -> None:
    PREFS_PATH.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
