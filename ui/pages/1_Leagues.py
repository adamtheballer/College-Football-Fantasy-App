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
        max-width: 1152px;
        margin: 0 auto;
        padding: 3rem 0 2.8rem;
        position: relative;
        z-index: 1;
    }

    .leagues-blob {
        position: absolute;
        border-radius: 999px;
        filter: blur(120px);
        opacity: 0.55;
        pointer-events: none;
        z-index: 0;
    }

    .leagues-blob--primary {
        width: 420px;
        height: 420px;
        top: 20%;
        left: -18%;
        background: rgba(92, 167, 255, 0.18);
    }

    .leagues-blob--secondary {
        width: 360px;
        height: 360px;
        bottom: 10%;
        right: -16%;
        background: rgba(54, 98, 180, 0.16);
    }

    .leagues-header {
        font-size: 3.75rem;
        font-weight: 800;
        font-style: italic;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        background: linear-gradient(120deg, #ffffff 0%, #ffffff 70%, rgba(92, 167, 255, 0.45) 100%);
        -webkit-background-clip: text;
        color: transparent;
        margin-bottom: 0.6rem;
    }

    .leagues-subtitle {
        color: #9fb0c7;
        font-size: 1.15rem;
        line-height: 1.6;
        margin-bottom: 1.6rem;
        max-width: 640px;
    }

    .leagues-create [data-testid="stButton"] button {
        width: 100%;
        min-width: 190px;
        border-radius: 18px;
        background: transparent;
        border: 1px solid rgba(92, 167, 255, 0.3);
        color: #7fb3ff;
        text-transform: uppercase;
        letter-spacing: 0.22em;
        font-size: 0.6rem;
        padding: 0.9rem 1.6rem;
    }

    .leagues-create {
        display: flex;
        justify-content: flex-end;
    }

    .leagues-create [data-testid="stButton"] button:hover {
        border-color: rgba(92, 167, 255, 0.7);
        background: rgba(92, 167, 255, 0.1);
        color: #e6f0ff;
    }

    .league-card {
        background: rgba(9, 14, 23, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 40px;
        padding: 0.4rem;
        margin-bottom: 2rem;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
        overflow: hidden;
    }

    .league-card [data-testid="stHorizontalBlock"] {
        gap: 0;
        align-items: stretch;
    }

    .league-card [data-testid="stHorizontalBlock"] > div {
        padding: 0 !important;
    }

    .league-card__panel {
        height: 100%;
        min-height: 200px;
        border-radius: 32px;
        padding: 2rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        position: relative;
        overflow: hidden;
    }

    .league-card__panel--left {
        background: linear-gradient(180deg, rgba(12, 18, 30, 0.96), rgba(10, 16, 26, 0.96));
    }

    .league-card__panel--mid {
        background: rgba(255, 255, 255, 0.04);
        border-left: 1px solid rgba(255, 255, 255, 0.06);
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }

    .league-card__panel--right {
        background: linear-gradient(135deg, rgba(92, 167, 255, 0.08), rgba(10, 16, 26, 0.1));
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .league-card__left {
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
        position: relative;
        z-index: 2;
    }

    .league-card__glow {
        position: absolute;
        width: 120px;
        height: 120px;
        top: -32px;
        left: -32px;
        border-radius: 50%;
        filter: blur(40px);
        opacity: 0.2;
        z-index: 1;
    }

    .league-card__glow--blue {
        background: rgba(92, 167, 255, 0.8);
    }

    .league-card__glow--orange {
        background: rgba(249, 115, 22, 0.7);
    }

    .league-card__glow--emerald {
        background: rgba(34, 197, 94, 0.7);
    }

    .league-card__icon {
        width: 48px;
        height: 48px;
        border-radius: 16px;
        color: #f5f9ff;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 0.9rem;
        box-shadow: 0 14px 24px rgba(0, 0, 0, 0.35);
    }

    .league-card__icon svg {
        width: 24px;
        height: 24px;
        stroke: #f5f9ff;
    }

    .league-card__icon--blue {
        background: linear-gradient(135deg, rgba(92, 167, 255, 0.95), rgba(59, 130, 246, 0.95));
    }

    .league-card__icon--orange {
        background: linear-gradient(135deg, rgba(249, 115, 22, 0.95), rgba(245, 158, 11, 0.95));
    }

    .league-card__icon--emerald {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.95), rgba(20, 184, 166, 0.95));
    }

    .league-card__name {
        font-size: 1.5rem;
        font-weight: 800;
        font-style: italic;
        text-transform: uppercase;
        color: #e6f0ff;
    }

    .league-card__meta {
        font-size: 0.62rem;
        letter-spacing: 0.2em;
        text-transform: uppercase;
        color: #7f8da3;
    }

    .league-card__members {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin-top: 1rem;
    }

    .league-card__avatars {
        display: flex;
        align-items: center;
    }

    .league-card__avatar {
        width: 24px;
        height: 24px;
        border-radius: 50%;
        border: 2px solid #050810;
        background: rgba(255, 255, 255, 0.04);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-left: -0.5rem;
        position: relative;
    }

    .league-card__avatar:first-child {
        margin-left: 0;
    }

    .league-card__avatar svg {
        width: 12px;
        height: 12px;
        stroke: rgba(255, 255, 255, 0.45);
    }

    .league-card__members-text {
        font-size: 0.55rem;
        letter-spacing: 0.24em;
        text-transform: uppercase;
        color: #7f8da3;
        margin-left: 0.3rem;
    }

    .league-standings {
        padding: 0.6rem 0;
    }

    .league-standings-title {
        font-size: 0.6rem;
        letter-spacing: 0.3em;
        text-transform: uppercase;
        color: rgba(127, 179, 255, 0.6);
        margin-bottom: 1rem;
    }

    .league-standings-row {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        align-items: center;
        font-size: 0.8rem;
        color: #e6f0ff;
        margin-bottom: 0.5rem;
        transition: transform 0.2s ease, color 0.2s ease;
    }

    .league-standings-row:last-child {
        margin-bottom: 0;
    }

    .league-standings-row:hover {
        transform: translateX(4px);
    }

    .league-standings-rank {
        color: #7f8da3;
        font-size: 0.6rem;
        letter-spacing: 0.08em;
        width: 18px;
    }

    .league-standings-team {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-weight: 700;
        flex: 1;
    }

    .league-standings-name {
        font-weight: 700;
    }

    .league-standings-row:hover .league-standings-team {
        color: #7fb3ff;
    }

    .league-standings-team .team-logo {
        width: 28px;
        height: 28px;
        font-size: 0.6rem;
        border-radius: 50%;
    }

    .league-standings-record {
        color: #7f8da3;
        font-size: 0.7rem;
        margin-left: 0.2rem;
    }

    .league-card__cta {
        height: 100%;
    }

    .league-card__cta [data-testid="stButton"] button {
        width: 100%;
        max-width: 220px;
        border-radius: 18px;
        background: rgba(92, 167, 255, 0.9);
        border: 1px solid rgba(92, 167, 255, 0.9);
        color: #0b1220;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-size: 0.6rem;
        padding: 0.85rem 2.4rem 0.85rem 1.6rem;
        position: relative;
        box-shadow: 0 10px 30px rgba(92, 167, 255, 0.2);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .league-card__cta [data-testid="stButton"] button::after {
        content: "\\203A";
        position: absolute;
        right: 1.1rem;
        top: 50%;
        transform: translateY(-50%);
        font-size: 0.9rem;
    }

    .league-card__cta [data-testid="stButton"] button:hover {
        background: rgba(92, 167, 255, 1);
        border-color: rgba(92, 167, 255, 1);
        color: #081019;
        transform: scale(1.03);
        box-shadow: 0 14px 34px rgba(92, 167, 255, 0.28);
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

st.markdown(
    "".join(
        [
            '<div class="leagues-shell">',
            '<div class="leagues-blob leagues-blob--primary"></div>',
            '<div class="leagues-blob leagues-blob--secondary"></div>',
        ]
    ),
    unsafe_allow_html=True,
)
top_left, top_right = st.columns([4.5, 1])
with top_left:
    st.markdown('<div class="leagues-header">Leagues</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="leagues-subtitle">Jump into a league or scan the standings preview. Compete with friends and rise through the ranks.</div>',
        unsafe_allow_html=True,
    )
with top_right:
    st.markdown('<div class="leagues-create">', unsafe_allow_html=True)
    if st.button("Create League +", key="create_league"):
        st.info("Create League is coming soon.")
    st.markdown("</div>", unsafe_allow_html=True)

if not leagues:
    st.info("No leagues available yet.")
else:
    for idx, league in enumerate(leagues):
        render_league_row(league, _jump_to_league, idx)

st.markdown("</div>", unsafe_allow_html=True)
