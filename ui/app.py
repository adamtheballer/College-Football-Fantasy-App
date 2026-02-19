import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.components.dashboard import (
    dashboard_card,
    empty_state,
    matchup_mini_card,
    news_list,
    power_rankings_table,
    skeleton_rows,
    team_mini_card,
)
from ui.lib.components.top_nav import render_top_nav
from ui.lib.components.ui import stat_pill
from ui.lib.components.sidebar import render_sidebar_nav
from ui.lib.mock.home import generate_home_data
from ui.lib.theme import apply_theme

st.set_page_config(page_title="Home", layout="wide")
apply_theme()
render_sidebar_nav("home")
render_top_nav("home")

st.markdown(
    """
    <style>
    .home-shell {
        max-width: 1200px;
        margin: 0 auto;
        padding-bottom: 2rem;
    }

    .dashboard-card {
        background: linear-gradient(150deg, #151a22 0%, #0f1319 100%);
        border: 1px solid #2a3444;
        border-radius: 16px;
        padding: 0.85rem 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.3);
    }

    .dashboard-card__header {
        font-size: 0.95rem;
        font-weight: 700;
        letter-spacing: 0.04rem;
        text-transform: uppercase;
        color: #8fb9ff;
        margin-bottom: 0.65rem;
    }

    .dashboard-card__body {
        display: flex;
        flex-direction: column;
        gap: 0.65rem;
    }

    .mini-row {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.45rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .mini-row:last-child {
        border-bottom: none;
        padding-bottom: 0;
    }

    .mini-title {
        font-weight: 600;
        color: #f3f6ff;
        font-size: 0.95rem;
    }

    .mini-sub {
        font-size: 0.72rem;
        color: #96a2b4;
    }

    .mini-row__meta {
        text-align: right;
    }

    .mini-stat,
    .mini-score {
        font-weight: 700;
        color: #e7f0ff;
        font-size: 0.9rem;
    }

    .rank-table {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
        font-size: 0.8rem;
    }

    .rank-row {
        display: grid;
        grid-template-columns: 32px 1fr 64px 56px;
        align-items: center;
        gap: 0.4rem;
        padding: 0.3rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .rank-header {
        color: #7f8da3;
        text-transform: uppercase;
        font-size: 0.68rem;
        letter-spacing: 0.05rem;
    }

    .rank-row:last-child {
        border-bottom: none;
    }

    .rank-cell.team {
        font-weight: 600;
        color: #f3f6ff;
    }

    .trend-up {
        color: #4bd37b;
        font-weight: 700;
    }

    .trend-down {
        color: #ff6b6b;
        font-weight: 700;
    }

    .trend-neutral {
        color: #a4afbf;
        font-weight: 700;
    }

    .news-item {
        padding: 0.4rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .news-item:last-child {
        border-bottom: none;
        padding-bottom: 0;
    }

    .news-title {
        font-weight: 600;
        color: #f3f6ff;
        font-size: 0.88rem;
    }

    .news-summary {
        font-size: 0.74rem;
        color: #9aa7bb;
        margin-top: 0.15rem;
    }

    .news-meta {
        font-size: 0.68rem;
        color: #76849a;
        margin-top: 0.25rem;
        text-transform: uppercase;
        letter-spacing: 0.05rem;
    }

    .skeleton-line {
        height: 10px;
        background: linear-gradient(90deg, #1a222d 0%, #2a3545 50%, #1a222d 100%);
        border-radius: 999px;
        animation: pulse 1.4s ease-in-out infinite;
        margin: 0.3rem 0;
    }

    .empty-state {
        color: #8a97ab;
        font-size: 0.78rem;
        padding: 0.5rem 0;
    }

    @keyframes pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

data = generate_home_data()
teams = data["teams"]
matchups = data["matchups"]
power_rankings = data["power_rankings"]
news_items = data["news"]

loading = st.session_state.get("home_loading", False)

st.markdown('<div class="home-shell">', unsafe_allow_html=True)

title_left, title_right = st.columns([3, 1])
with title_left:
    st.title("College Football Fantasy")
    st.caption("Fantasy football research + roster helper.")
with title_right:
    st.markdown(stat_pill("2024 Season", "primary"), unsafe_allow_html=True)

left_col, right_col = st.columns(2)

with left_col:
    if loading:
        teams_html = skeleton_rows(4)
    elif teams:
        teams_html = "".join(team_mini_card(team) for team in teams)
    else:
        teams_html = empty_state("No teams yet.")
    st.markdown(dashboard_card("My Teams", teams_html), unsafe_allow_html=True)

    if loading:
        rankings_html = skeleton_rows(6)
    else:
        rankings_html = power_rankings_table(power_rankings)
    st.markdown(dashboard_card("Power Rankings", rankings_html), unsafe_allow_html=True)

with right_col:
    if loading:
        matchups_html = skeleton_rows(4)
    elif matchups:
        matchups_html = "".join(matchup_mini_card(matchup) for matchup in matchups)
    else:
        matchups_html = empty_state("No live matchups.")
    st.markdown(dashboard_card("Live Matchups", matchups_html), unsafe_allow_html=True)

    if loading:
        news_html = skeleton_rows(4)
    else:
        news_html = news_list(news_items)
    st.markdown(dashboard_card("League News", news_html), unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
