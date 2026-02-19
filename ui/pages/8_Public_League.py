import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.components.sidebar import render_sidebar_nav
from ui.lib.components.top_nav import render_top_nav
from ui.lib.mock.public import generate_public_league
from ui.lib.team_branding import team_logo_html
from ui.lib.theme import apply_theme

st.set_page_config(page_title="Public League", layout="wide")
apply_theme()
render_sidebar_nav("public")
render_top_nav("scoreboard")

st.markdown(
    """
    <style>
    .public-shell {
        max-width: 1100px;
        margin: 0 auto;
        padding-bottom: 2rem;
    }

    .public-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
        margin-bottom: 1rem;
    }

    .public-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }

    .public-row {
        display: grid;
        grid-template-columns: 2fr 0.7fr 0.7fr;
        gap: 0.4rem;
        align-items: center;
        font-size: 0.78rem;
        padding: 0.3rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .public-row:last-child {
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
public_id = params.get("publicId")
if isinstance(public_id, list):
    public_id = public_id[0] if public_id else None

if not public_id:
    st.info("Missing publicId. Paste a public league link to view.")
    st.stop()

data = generate_public_league(public_id)
league = data["league"]

st.markdown('<div class="public-shell">', unsafe_allow_html=True)
st.title(f"Public League: {league['name']}")
st.caption("Read-only view · owner details hidden")

standings_rows = []
for index, team in enumerate(data["standings"], start=1):
    standings_rows.append(
        f"""
        <div class="public-row">
            <div>{index}. {team_logo_html(team['name'])} {team['name']}</div>
            <div>{team['record']}</div>
            <div>{team['points_for']}</div>
        </div>
        """
    )
st.markdown(
    f'<div class="public-card"><div class="public-title">Standings</div>{"".join(standings_rows)}</div>',
    unsafe_allow_html=True,
)

schedule_rows = []
for week, matchups in data["schedule"].items():
    for matchup in matchups:
        schedule_rows.append(
            f"""
            <div class="public-row">
                <div>Week {week}: {team_logo_html(matchup['away'])} {matchup['away']} at {team_logo_html(matchup['home'])} {matchup['home']}</div>
                <div>{matchup['away_score']} - {matchup['home_score']}</div>
                <div>Proj {matchup['away_proj']} / {matchup['home_proj']}</div>
            </div>
            """
        )
st.markdown(
    f'<div class="public-card"><div class="public-title">Schedule</div>{"".join(schedule_rows)}</div>',
    unsafe_allow_html=True,
)

performer_rows = []
for player in data["top_performers"]:
    performer_rows.append(
        f"""
        <div class="public-row">
            <div>{player['name']} ({player['pos']})</div>
            <div>{player['team']}</div>
            <div>Proj {player['proj']}</div>
        </div>
        """
    )
st.markdown(
    f'<div class="public-card"><div class="public-title">Top Performers</div>{"".join(performer_rows)}</div>',
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)
