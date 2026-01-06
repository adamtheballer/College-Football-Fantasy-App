import os
import random
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib import api_client
from ui.lib.theme import apply_theme


def _get_team_on_clock(order: list[dict], pick_index: int, snake: bool) -> tuple[dict, int, int]:
    team_count = len(order)
    round_index = pick_index // team_count
    pick_in_round = pick_index % team_count
    if snake and round_index % 2 == 1:
        team_index = team_count - 1 - pick_in_round
    else:
        team_index = pick_in_round
    return order[team_index], round_index + 1, pick_in_round + 1


def _format_player_label(player: dict) -> str:
    return f"{player['name']} - {player['position']} ({player['school']})"


st.header("Draft")
apply_theme()

try:
    leagues = api_client.get_leagues()["data"]
except Exception as exc:
    st.error(f"Failed to load leagues: {exc}")
    st.stop()

league_options = {f"{league['name']} (#{league['id']})": league for league in leagues}
selected_label = st.selectbox("Select league", list(league_options.keys()) if league_options else [])
selected_league = league_options.get(selected_label)

if not selected_league:
    st.info("Create a league to start a draft.")
    st.stop()

try:
    teams = api_client.get_teams(selected_league["id"])["data"]
except Exception as exc:
    st.error(f"Failed to load teams: {exc}")
    st.stop()

if len(teams) < 2:
    st.info("Add at least two teams to start a draft.")
    st.stop()

try:
    players = api_client.get_players({"limit": 500})["data"]
except Exception as exc:
    st.error(f"Failed to load players: {exc}")
    st.stop()

draft_state = st.session_state.get("draft_state")
if draft_state and draft_state.get("league_id") != selected_league["id"]:
    st.warning("Draft state is for another league. Reset to start a new draft.")

setup_col, status_col = st.columns([2, 1])
with setup_col:
    with st.form("draft_setup"):
        rounds = st.number_input("Rounds", min_value=1, max_value=30, value=10, step=1)
        snake = st.checkbox("Snake draft", value=True)
        order_mode = st.selectbox("Order", ["Randomize", "Alphabetical"])
        submitted = st.form_submit_button("Start draft")

    if submitted:
        draft_order = [{"id": team["id"], "name": team["name"]} for team in teams]
        if order_mode == "Randomize":
            random.shuffle(draft_order)
        else:
            draft_order = sorted(draft_order, key=lambda item: item["name"].lower())
        st.session_state["draft_state"] = {
            "league_id": selected_league["id"],
            "rounds": int(rounds),
            "snake": snake,
            "order": draft_order,
            "picks": [],
            "status": "active",
        }
        draft_state = st.session_state["draft_state"]
        st.success("Draft started.")

with status_col:
    if draft_state:
        total_picks = draft_state["rounds"] * len(draft_state["order"])
        pick_index = len(draft_state["picks"])
        if pick_index < total_picks:
            team_on_clock, round_number, pick_in_round = _get_team_on_clock(
                draft_state["order"], pick_index, draft_state["snake"]
            )
            st.metric("On the clock", team_on_clock["name"])
            st.write(f"Round {round_number}, Pick {pick_in_round} of {len(draft_state['order'])}")
        else:
            st.success("Draft complete.")

if not draft_state:
    st.stop()

total_picks = draft_state["rounds"] * len(draft_state["order"])
pick_index = len(draft_state["picks"])

st.subheader("Draft order")
order_labels = [f"{index + 1}. {team['name']}" for index, team in enumerate(draft_state["order"])]
st.write("\n".join(order_labels))

st.subheader("Make pick")
drafted_player_ids = {pick["player_id"] for pick in draft_state["picks"]}
filter_col, search_col = st.columns([1, 2])
with filter_col:
    position_filter = st.selectbox("Position", ["", "QB", "RB", "WR", "TE", "K", "DST"])
with search_col:
    search = st.text_input("Search player")

available_players = [
    player
    for player in players
    if player["id"] not in drafted_player_ids
    and (not position_filter or player["position"] == position_filter)
    and (not search.strip() or search.strip().lower() in player["name"].lower())
]

if pick_index >= total_picks:
    st.info("Draft is complete.")
else:
    team_on_clock, round_number, pick_in_round = _get_team_on_clock(
        draft_state["order"], pick_index, draft_state["snake"]
    )
    if not available_players:
        st.info("No available players match the current filters.")
    else:
        with st.form("make_pick"):
            player_labels = [_format_player_label(player) for player in available_players]
            selected_label = st.selectbox("Available players", player_labels)
            submitted = st.form_submit_button("Draft player")

        if submitted:
            selected_index = player_labels.index(selected_label)
            player = available_players[selected_index]
            draft_state["picks"].append(
                {
                    "pick_number": pick_index + 1,
                    "round": round_number,
                    "team_id": team_on_clock["id"],
                    "team_name": team_on_clock["name"],
                    "player_id": player["id"],
                    "player_name": player["name"],
                    "position": player["position"],
                    "school": player["school"],
                }
            )
            st.session_state["draft_state"] = draft_state
            st.success(f"{team_on_clock['name']} drafted {player['name']}.")

action_col, reset_col = st.columns([1, 1])
with action_col:
    if st.button("Undo last pick") and draft_state["picks"]:
        removed = draft_state["picks"].pop()
        st.session_state["draft_state"] = draft_state
        st.info(f"Removed pick: {removed['player_name']} ({removed['team_name']}).")
with reset_col:
    if st.button("Reset draft"):
        st.session_state.pop("draft_state", None)
        st.warning("Draft reset. Start a new draft to continue.")
        st.stop()

st.subheader("Draft board")
if draft_state["picks"]:
    st.dataframe(draft_state["picks"], use_container_width=True)
else:
    st.info("No picks made yet.")

st.subheader("Apply picks to rosters")
if st.button("Add drafted players to rosters"):
    failures = []
    for pick in draft_state["picks"]:
        try:
            api_client.add_roster_entry(
                pick["team_id"],
                {
                    "player_id": pick["player_id"],
                    "slot": pick["position"],
                    "status": "bench",
                },
            )
        except Exception as exc:
            failures.append(f"{pick['player_name']} -> {pick['team_name']}: {exc}")
    if failures:
        st.error("Some roster adds failed.")
        st.write("\n".join(failures))
    else:
        st.success("Drafted players added to rosters.")
