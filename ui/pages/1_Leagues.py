import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.components.leagues import render_league_row
from ui.lib.components.sidebar import render_sidebar_nav
from ui.lib.components.top_nav import render_top_nav
from ui.lib.mock.leagues import generate_leagues_data
from ui.lib.theme import apply_theme

st.set_page_config(page_title="Leagues", layout="wide")
apply_theme()
render_sidebar_nav("leagues")
render_top_nav("league")

st.markdown(
    """
    <style>
    .leagues-shell {
        max-width: 1200px;
        margin: 0 auto;
        padding-bottom: 2rem;
    }

    .leagues-header {
        font-size: 1.4rem;
        font-weight: 700;
        margin-bottom: 0.4rem;
    }

    .leagues-subtitle {
        color: #9aa7bb;
        font-size: 0.85rem;
        margin-bottom: 1.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _jump_to_league(league_id: int) -> None:
    st.session_state["selected_league_id"] = league_id
    st.session_state["nav_target_tab"] = "My Team"
    if hasattr(st, "switch_page"):
        st.switch_page("pages/2_League.py")
    else:
        st.info("Open the League page from the sidebar to continue.")


data = generate_leagues_data()
leagues = data["leagues"]

st.markdown('<div class="leagues-shell">', unsafe_allow_html=True)
st.markdown('<div class="leagues-header">Leagues</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="leagues-subtitle">Jump into a league or scan the standings preview.</div>',
    unsafe_allow_html=True,
)

if not leagues:
    st.info("No leagues available yet.")
else:
    for league in leagues:
        render_league_row(league, _jump_to_league)

st.markdown("</div>", unsafe_allow_html=True)
