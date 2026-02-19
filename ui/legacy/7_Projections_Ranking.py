import json
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.projection_scoring import resolve_scoring_rules, score_projection
from ui.lib.theme import apply_theme

DATA_PATH = os.path.join(ROOT_DIR, "ui", "data", "projections.json")


def _load_projections(path: str) -> list[dict]:
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        st.error("Projections file is not valid JSON.")
        return []
    if not isinstance(data, list):
        st.error("Projections file must contain a list of player projections.")
        return []
    return data


def _projection_label(projection: dict) -> str:
    return json.dumps(projection, sort_keys=True)


st.header("Projections Ranking")
apply_theme()

projections = _load_projections(DATA_PATH)
if not projections:
    st.info("No projections found. Add data to ui/data/projections.json.")
    st.stop()

positions = sorted({entry.get("position") for entry in projections if entry.get("position")})
teams = sorted({entry.get("team") for entry in projections if entry.get("team")})

filter_col, team_col, scoring_col = st.columns(3)
with filter_col:
    position_filter = st.selectbox("Position", ["All"] + positions)
with team_col:
    team_filter = st.selectbox("Team", ["All"] + teams)
with scoring_col:
    scoring_type = st.selectbox("Scoring preset", ["standard", "half_ppr", "ppr"], index=0)

rules = resolve_scoring_rules(scoring_type)
rows = []
for entry in projections:
    projection = entry.get("projection") or {}
    rows.append(
        {
            "player": entry.get("player", "Unknown"),
            "team": entry.get("team", ""),
            "position": entry.get("position", ""),
            "projection": _projection_label(projection),
            "fantasy_points": score_projection(projection, rules=rules, strict=False),
        }
    )

if position_filter != "All":
    rows = [row for row in rows if row["position"] == position_filter]
if team_filter != "All":
    rows = [row for row in rows if row["team"] == team_filter]

rows = sorted(rows, key=lambda row: row["fantasy_points"], reverse=True)

if not rows:
    st.info("No projections match the selected filters.")
else:
    st.caption(f"Scoring preset: {scoring_type}")
    st.dataframe(rows, use_container_width=True)
