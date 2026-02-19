import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.components.sidebar import render_sidebar_nav
from ui.lib.components.top_nav import render_top_nav
from ui.lib.mock.player_detail import generate_player_detail
from ui.lib.mock.players import generate_players_data
from ui.lib.theme import apply_theme

st.set_page_config(page_title="Player", layout="wide")
apply_theme()
render_sidebar_nav("players")
render_top_nav("players")

st.markdown(
    """
    <style>
    .player-shell {
        max-width: 1100px;
        margin: 0 auto;
        padding-bottom: 2rem;
    }

    .player-header {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    .player-name {
        font-size: 1.6rem;
        font-weight: 800;
        color: #f3f6ff;
    }

    .player-meta {
        color: #9aa7bb;
        font-size: 0.85rem;
        margin-top: 0.2rem;
    }

    .player-news {
        margin-top: 0.6rem;
        font-size: 0.78rem;
        color: #c8d4e6;
    }

    .player-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
        margin-bottom: 1rem;
    }

    .player-card-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }

    .game-log {
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
        font-size: 0.75rem;
    }

    .game-row {
        display: grid;
        grid-template-columns: 0.6fr 1.2fr 0.8fr 0.6fr 0.6fr;
        gap: 0.4rem;
        align-items: center;
        padding: 0.3rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .game-row:last-child {
        border-bottom: none;
    }

    .game-header {
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-size: 0.62rem;
        color: #7f8da3;
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
player_id_param = params.get("playerId")
if isinstance(player_id_param, list):
    player_id_param = player_id_param[0] if player_id_param else None

player_id = st.session_state.get("selected_player_id")
player_seed = st.session_state.get("players_seed_0")

if player_id is None and player_id_param:
    try:
        player_id = int(player_id_param)
    except ValueError:
        player_id = None

if player_id is None:
    st.info("Select a player from the Players tab to continue.")
    st.stop()

players_data = generate_players_data(player_seed or str(player_id))
player = next((item for item in players_data["players"] if item["id"] == player_id), None)
if player is None:
    st.info("Player not found.")
    st.stop()

detail = generate_player_detail(player)

st.markdown('<div class="player-shell">', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="player-header">
        <div class="player-name">{player['name']}</div>
        <div class="player-meta">{player['team']} · {player['conf']} · {player['pos']}</div>
        <div class="player-news">{detail['news']}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

main_col, side_col = st.columns([2, 1])

with main_col:
    st.markdown('<div class="player-card"><div class="player-card-title">Game Log</div>', unsafe_allow_html=True)
    header = (
        '<div class="game-row game-header"><div>Week</div><div>Opp</div><div>Status</div><div>Pts</div><div>Proj</div></div>'
    )
    rows = []
    for game in detail["game_log"]:
        rows.append(
            "".join(
                [
                    '<div class="game-row">',
                    f"<div>{game['week']}</div>",
                    f"<div>{game['opp']}</div>",
                    f"<div>{game['status']}</div>",
                    f"<div>{game['points']}</div>",
                    f"<div>{game['proj']}</div>",
                    "</div>",
                ]
            )
        )
    st.markdown(f'<div class="game-log">{header}{"".join(rows)}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with side_col:
    st.markdown('<div class="player-card"><div class="player-card-title">Trend (Last 6)</div>', unsafe_allow_html=True)
    if detail["trend_points"]:
        st.line_chart(detail["trend_points"], height=160)
    else:
        st.caption("No trend data.")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
