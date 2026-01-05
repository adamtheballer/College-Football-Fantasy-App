import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib import api_client
from ui.lib.theme import apply_theme

st.header("Rosters")
apply_theme()

try:
    leagues = api_client.get_leagues()["data"]
except Exception as exc:
    st.error(f"Failed to load leagues: {exc}")
    st.stop()

league_options = {f"{league['name']} (#{league['id']})": league for league in leagues}
selected_league_label = st.selectbox("Select league", list(league_options.keys()) if league_options else [])
selected_league = league_options.get(selected_league_label)

if not selected_league:
    st.info("Create a league to manage rosters.")
    st.stop()

try:
    teams = api_client.get_teams(selected_league["id"])["data"]
except Exception as exc:
    st.error(f"Failed to load teams: {exc}")
    st.stop()

team_options = {f"{team['name']} (#{team['id']})": team for team in teams}
selected_team_label = st.selectbox("Select team", list(team_options.keys()) if team_options else [])
selected_team = team_options.get(selected_team_label)

if not selected_team:
    st.info("Add a team to manage its roster.")
    st.stop()

st.subheader("Add player to roster")

try:
    players = api_client.get_players({"limit": 200})["data"]
except Exception as exc:
    st.error(f"Failed to load players: {exc}")
    st.stop()

if not players:
    st.info("Add players before building a roster.")
    st.stop()

player_options = {f"{player['name']} - {player['position']} ({player['school']})": player for player in players}
selected_player_label = st.selectbox("Player", list(player_options.keys()) if player_options else [])

with st.form("add_roster_entry"):
    slot = st.text_input("Slot", value="QB")
    status = st.selectbox("Status", ["active", "bench", "ir"])
    submitted = st.form_submit_button("Add to roster")

if submitted:
    player = player_options.get(selected_player_label)
    if not player:
        st.error("Select a player.")
    else:
        with st.spinner("Adding player..."):
            try:
                api_client.add_roster_entry(
                    selected_team["id"],
                    {"player_id": player["id"], "slot": slot.strip(), "status": status},
                )
                st.success("Player added.")
            except Exception as exc:
                st.error(f"Failed to add player: {exc}")

st.subheader("Current roster")
try:
    roster_data = api_client.get_roster(selected_team["id"])
    roster_entries = roster_data["data"]
    st.dataframe(
        [
            {
                "id": entry["id"],
                "player": entry["player"]["name"],
                "position": entry["player"]["position"],
                "school": entry["player"]["school"],
                "slot": entry["slot"],
                "status": entry["status"],
            }
            for entry in roster_entries
        ],
        use_container_width=True,
    )

    if roster_entries:
        st.subheader("Remove roster entry")
        remove_options = {f"{entry['player']['name']} (#{entry['id']})": entry for entry in roster_entries}
        remove_label = st.selectbox("Roster entry", list(remove_options.keys()))
        if st.button("Remove"):
            entry = remove_options[remove_label]
            with st.spinner("Removing player..."):
                try:
                    api_client.delete_roster_entry(selected_team["id"], entry["id"])
                    st.success("Removed.")
                except Exception as exc:
                    st.error(f"Failed to remove player: {exc}")
except Exception as exc:
    st.error(f"Failed to load roster: {exc}")
