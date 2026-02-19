import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.components.sidebar import render_sidebar_nav
from ui.lib.components.top_nav import render_top_nav
from ui.lib.mock.league import generate_league_data
from ui.lib.mock.team import generate_team_data
from ui.lib.theme import apply_theme
from ui.lib.team_branding import team_logo_html

st.set_page_config(page_title="Team", layout="wide")
apply_theme()
render_sidebar_nav("league")
render_top_nav("team")

st.markdown(
    """
    <style>
    .team-shell {
        max-width: 1200px;
        margin: 0 auto;
        padding-bottom: 2rem;
    }

    .team-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }

    .team-title {
        font-size: 1.6rem;
        font-weight: 800;
        color: #f3f6ff;
    }

    .team-meta {
        color: #9aa7bb;
        font-size: 0.85rem;
    }

    .roster-section {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
        margin-bottom: 1rem;
    }

    .roster-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.5rem;
    }

    .roster-table {
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
        font-size: 0.75rem;
    }

    .roster-row {
        display: grid;
        grid-template-columns: 1.8fr 0.6fr 0.6fr 0.6fr 0.6fr;
        gap: 0.4rem;
        align-items: center;
        padding: 0.3rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .roster-row:last-child {
        border-bottom: none;
    }

    .roster-header {
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-size: 0.62rem;
        color: #7f8da3;
    }

    .roster-name {
        font-weight: 600;
        color: #f3f6ff;
    }

    .side-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
        margin-bottom: 1rem;
    }

    .side-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }

    .schedule-row,
    .transaction-row {
        display: flex;
        justify-content: space-between;
        font-size: 0.75rem;
        padding: 0.3rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .schedule-row:last-child,
    .transaction-row:last-child {
        border-bottom: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _get_query_params() -> dict:
    if hasattr(st, "query_params"):
        return dict(st.query_params)
    return st.experimental_get_query_params()


params = _get_query_params()
league_id_param = params.get("leagueId")
team_id_param = params.get("teamId")
if isinstance(league_id_param, list):
    league_id_param = league_id_param[0] if league_id_param else None
if isinstance(team_id_param, list):
    team_id_param = team_id_param[0] if team_id_param else None

league_id = st.session_state.get("selected_league_id")
team_id = st.session_state.get("selected_team_id")

if league_id is None and league_id_param:
    try:
        league_id = int(league_id_param)
    except ValueError:
        league_id = None

if team_id is None and team_id_param:
    try:
        team_id = int(team_id_param)
    except ValueError:
        team_id = None

if league_id is None or team_id is None:
    st.info("Select a team from the League page to continue.")
    st.stop()

st.session_state["selected_league_id"] = league_id
st.session_state["selected_team_id"] = team_id

league_data = generate_league_data(league_id)
league = league_data["league"]
team = next((item for item in league["teams"] if item["id"] == team_id), None)
if team is None:
    st.info("Team not found.")
    st.stop()

team_data = generate_team_data(league, team)

st.markdown('<div class="team-shell">', unsafe_allow_html=True)

header_left, header_right = st.columns([3, 1])
with header_left:
    st.markdown(
        f'<div class="team-title">{team_logo_html(team["name"], 34)} {team["name"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="team-meta">{league["name"]} · {team["record"]} · {team["owner"]}</div>',
        unsafe_allow_html=True,
    )
with header_right:
    if st.button("Back to League"):
        st.session_state["selected_league_id"] = league_id
        if hasattr(st, "switch_page"):
            st.switch_page("pages/2_League.py")
        else:
            st.info("Open the League page from the sidebar to continue.")

main_col, side_col = st.columns([2.4, 1])

with main_col:
    roster = team_data["roster"]
    for title, rows in [
        ("Starters", roster["starters"]),
        ("Bench", roster["bench"]),
        ("IR", roster["ir"]),
    ]:
        st.markdown(f'<div class="roster-section"><div class="roster-title">{title}</div>', unsafe_allow_html=True)
        if not rows:
            st.info("No players listed.")
        else:
            header = (
                '<div class="roster-row roster-header">'
                "<div>Player</div><div>Pos</div><div>Pts</div><div>Proj</div><div>Status</div>"
                "</div>"
            )
            body = []
            for player in rows:
                body.append(
                    f"""
                    <div class="roster-row">
                        <div class="roster-name">{player['name']}<br/><span class="team-meta">{player['team']} · {player['slot']}</span></div>
                        <div>{player['pos']}</div>
                        <div>{player['points']}</div>
                        <div>{player['proj']}</div>
                        <div>{player['status']}</div>
                    </div>
                    """
                )
            st.markdown(f'<div class="roster-table">{header}{"".join(body)}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="roster-section"><div class="roster-title">Recent Performance</div>', unsafe_allow_html=True)
    performance = team_data["recent_performance"]
    if performance:
        points = [item["points"] for item in performance]
        st.line_chart(points, height=160)
        st.caption("Weeks: " + ", ".join(str(item["week"]) for item in performance))
    else:
        st.info("No recent performance available.")
    st.markdown("</div>", unsafe_allow_html=True)

with side_col:
    st.markdown('<div class="side-card"><div class="side-title">Remaining Schedule</div>', unsafe_allow_html=True)
    schedule = team_data["schedule"]
    if schedule:
        for item in schedule:
            st.markdown(
                f'<div class="schedule-row"><span>Week {item["week"]} vs {item["opponent"]}</span><span>{item["projection"]} proj</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No upcoming games.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="side-card"><div class="side-title">Recent Transactions</div>', unsafe_allow_html=True)
    transactions = team_data["transactions"]
    if transactions:
        for item in transactions:
            st.markdown(
                f'<div class="transaction-row"><span>{item["detail"]}</span><span>{item["time"]}</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No recent activity.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="side-card"><div class="side-title">Start/Sit Optimizer</div>', unsafe_allow_html=True)
    start_sit = team_data.get("start_sit", [])
    if start_sit:
        for suggestion in start_sit:
            st.markdown(
                f'<div class="schedule-row"><span>Start {suggestion["start"]}</span><span>+{suggestion["delta"]} pts</span></div>',
                unsafe_allow_html=True,
            )
            st.caption(f"Sit {suggestion['sit']}")
    else:
        st.caption("No recommended swaps right now.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
