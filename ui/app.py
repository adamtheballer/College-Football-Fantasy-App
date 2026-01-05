import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.theme import apply_theme

st.set_page_config(page_title="CollegeFootballFantasy", layout="wide")
apply_theme()

st.title("CollegeFootballFantasy")
st.write("Research + roster helper for college fantasy leagues.")

st.markdown(
    """
Use the left navigation to manage leagues, teams, rosters, and players.

- Leagues: create or inspect leagues.
- Teams: add teams under a league.
- Rosters: assign players to a team.
- Players: search and add players.
    """
)
