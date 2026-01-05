import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib import api_client
from ui.lib.theme import apply_theme

st.header("Teams")
apply_theme()

try:
    leagues = api_client.get_leagues()["data"]
except Exception as exc:
    st.error(f"Failed to load leagues: {exc}")
    st.stop()

league_options = {f"{league['name']} (#{league['id']})": league for league in leagues}
selected_label = st.selectbox("Select league", list(league_options.keys()) if league_options else [])
selected_league = league_options.get(selected_label)

if selected_league:
    with st.form("create_team"):
        name = st.text_input("Team name")
        owner_name = st.text_input("Owner name (optional)")
        submitted = st.form_submit_button("Add team")

    if submitted:
        if not name.strip():
            st.error("Team name is required.")
        else:
            with st.spinner("Creating team..."):
                try:
                    api_client.create_team(
                        selected_league["id"],
                        {"name": name.strip(), "owner_name": owner_name.strip() or None},
                    )
                    st.success("Team created.")
                except Exception as exc:
                    st.error(f"Failed to create team: {exc}")

    st.subheader("Teams in league")
    try:
        data = api_client.get_teams(selected_league["id"])
        st.dataframe(data["data"], use_container_width=True)
    except Exception as exc:
        st.error(f"Failed to load teams: {exc}")
else:
    st.info("Create a league to get started.")
