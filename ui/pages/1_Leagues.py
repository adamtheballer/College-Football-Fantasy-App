import json
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib import api_client
from ui.lib.theme import apply_theme

st.header("Leagues")
apply_theme()

default_roster_limits = {
    "qb": 1,
    "rb": 2,
    "wr": 2,
    "te": 1,
    "flex": 1,
    "k": 1,
    "dst": 1,
    "bench": 5,
}
default_scoring_rules = {
    "pass_td": 4,
    "rush_td": 6,
    "rec_td": 6,
    "pass_yd": 0.04,
    "rush_yd": 0.1,
    "rec_yd": 0.1,
}

with st.form("create_league"):
    name = st.text_input("League name")
    size = st.number_input("League size", min_value=2, max_value=24, value=10, step=1)
    season_start_week = st.number_input("Season start week", min_value=1, max_value=17, value=1, step=1)
    platform = st.selectbox("Platform", ["espn", "yahoo", "sleeper", "cfbd"])
    scoring_type = st.text_input("Scoring type", value="standard")
    with st.expander("Advanced settings", expanded=False):
        roster_limits = st.text_area(
            "Roster limits (JSON)",
            value=json.dumps(default_roster_limits, indent=2),
            help="Currently displayed for UX planning; not persisted yet.",
        )
        scoring_rules = st.text_area(
            "Scoring rules (JSON)",
            value=json.dumps(default_scoring_rules, indent=2),
            help="Currently displayed for UX planning; not persisted yet.",
        )
    submitted = st.form_submit_button("Create league")

if submitted:
    if not name.strip():
        st.error("League name is required.")
    elif size < 2:
        st.error("League size must be at least 2.")
    else:
        with st.spinner("Creating league..."):
            try:
                api_client.create_league(
                    {
                        "name": name.strip(),
                        "platform": platform,
                        "scoring_type": scoring_type.strip(),
                    }
                )
                st.success("League created.")
                st.info(
                    "League size, start week, roster limits, and scoring rules are visible in the UI but not yet saved."
                )
            except Exception as exc:
                st.error(f"Failed to create league: {exc}")

st.subheader("Existing leagues")
try:
    data = api_client.get_leagues()
    leagues = data["data"]
    st.dataframe(leagues, use_container_width=True)
except Exception as exc:
    st.error(f"Failed to load leagues: {exc}")
    leagues = []

st.subheader("League settings")
league_options = {f"{league['name']} (#{league['id']})": league for league in leagues}
selected_label = st.selectbox("Select league to edit", list(league_options.keys()) if league_options else [])
selected_league = league_options.get(selected_label)

if selected_league:
    with st.form("update_league"):
        edit_name = st.text_input("League name", value=selected_league["name"])
        edit_platform = st.selectbox(
            "Platform",
            ["espn", "yahoo", "sleeper", "cfbd"],
            index=["espn", "yahoo", "sleeper", "cfbd"].index(selected_league["platform"]),
        )
        edit_scoring_type = st.text_input("Scoring type", value=selected_league["scoring_type"])
        with st.expander("Advanced settings", expanded=False):
            st.text_area(
                "Roster limits (JSON)",
                value=json.dumps(default_roster_limits, indent=2),
                help="Editing is disabled until league settings are persisted in the API.",
                disabled=True,
            )
            st.text_area(
                "Scoring rules (JSON)",
                value=json.dumps(default_scoring_rules, indent=2),
                help="Editing is disabled until league settings are persisted in the API.",
                disabled=True,
            )
        updated = st.form_submit_button("Save settings")

    if updated:
        if not edit_name.strip():
            st.error("League name is required.")
        else:
            with st.spinner("Saving settings..."):
                try:
                    api_client.update_league(
                        selected_league["id"],
                        {
                            "name": edit_name.strip(),
                            "platform": edit_platform,
                            "scoring_type": edit_scoring_type.strip(),
                        },
                    )
                    st.success("League updated.")
                except Exception as exc:
                    st.error(f"Failed to update league: {exc}")
else:
    st.info("Create a league to configure settings.")
