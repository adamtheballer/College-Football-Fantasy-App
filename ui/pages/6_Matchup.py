import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.theme import apply_theme


st.header("Matchup")
apply_theme()

st.markdown(
    """
    <style>
    .matchup-shell {
        max-width: 900px;
        margin: 0 auto;
    }
    .matchup-topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.5rem 0;
    }
    .matchup-league {
        font-size: 1.1rem;
        font-weight: 700;
    }
    .matchup-tabs {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.5rem;
        border-bottom: 1px solid #1f1f1f;
        margin-bottom: 1rem;
    }
    .matchup-tab {
        text-align: center;
        padding: 0.6rem 0;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.12rem;
        color: #9a9a9a;
        border-bottom: 3px solid transparent;
    }
    .matchup-tab.active {
        color: #ededed;
        border-bottom-color: #2ed158;
    }
    .matchup-subtabs {
        display: flex;
        gap: 0.5rem;
        margin: 0.75rem 0 1rem;
    }
    .matchup-pill {
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        border: 1px solid #2c2c2c;
        color: #bdbdbd;
        font-size: 0.75rem;
        background: #151515;
    }
    .matchup-pill.active {
        border-color: #4aa3ff;
        color: #4aa3ff;
    }
    .matchup-scorecard {
        background: #1a1a1a;
        border: 1px solid #232323;
        border-radius: 16px;
        padding: 1rem;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
    }
    .team-score {
        text-align: center;
    }
    .team-score h2 {
        margin: 0.2rem 0;
        font-size: 2rem;
    }
    .team-score p {
        margin: 0;
        color: #9a9a9a;
        font-size: 0.8rem;
    }
    .prob-bar {
        margin-top: 0.75rem;
        background: #222;
        border-radius: 999px;
        overflow: hidden;
        height: 8px;
        display: flex;
    }
    .prob-left {
        background: #4aa3ff;
        width: 50%;
    }
    .prob-right {
        background: #2ed158;
        width: 50%;
    }
    .section-title {
        margin: 1.5rem 0 0.5rem;
        text-transform: uppercase;
        font-size: 0.8rem;
        letter-spacing: 0.1rem;
        color: #9a9a9a;
    }
    .roster-row {
        display: grid;
        grid-template-columns: 60px 1fr 60px;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem;
        background: #1a1a1a;
        border: 1px solid #232323;
        border-radius: 14px;
        margin-bottom: 0.6rem;
    }
    .pos-pill {
        width: 52px;
        height: 32px;
        border-radius: 16px;
        border: 1px solid #4aa3ff;
        color: #4aa3ff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .player-meta h4 {
        margin: 0;
        font-size: 0.95rem;
        color: #ededed;
    }
    .player-meta p {
        margin: 0.2rem 0 0;
        font-size: 0.75rem;
        color: #9a9a9a;
    }
    .player-score {
        text-align: right;
        font-weight: 700;
        color: #ededed;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="matchup-shell">
        <div class="matchup-topbar">
            <div class="matchup-league">Sunday League Showdown</div>
            <div class="matchup-pill">Week 1</div>
        </div>
        <div class="matchup-tabs">
            <div class="matchup-tab">Roster</div>
            <div class="matchup-tab active">Matchup</div>
            <div class="matchup-tab">Players</div>
            <div class="matchup-tab">League</div>
        </div>
        <div class="matchup-subtabs">
            <div class="matchup-pill">League Scores</div>
            <div class="matchup-pill active">Home vs Away</div>
            <div class="matchup-pill">All Matchups</div>
        </div>
        <div class="matchup-scorecard">
            <div class="team-score">
                <h2>0.0</h2>
                <p>Home Sharks</p>
            </div>
            <div class="team-score">
                <h2>0.0</h2>
                <p>Away Wolves</p>
            </div>
            <div class="prob-bar">
                <div class="prob-left"></div>
                <div class="prob-right"></div>
            </div>
            <div class="prob-bar">
                <div class="prob-left"></div>
                <div class="prob-right"></div>
            </div>
        </div>
        <div class="section-title">Starters</div>
        <div class="roster-row">
            <div class="pos-pill">QB</div>
            <div class="player-meta">
                <h4>Quarterback Slot</h4>
                <p>Awaiting roster</p>
            </div>
            <div class="player-score">0.0</div>
        </div>
        <div class="roster-row">
            <div class="pos-pill">RB</div>
            <div class="player-meta">
                <h4>Running Back Slot</h4>
                <p>Awaiting roster</p>
            </div>
            <div class="player-score">0.0</div>
        </div>
        <div class="roster-row">
            <div class="pos-pill">WR</div>
            <div class="player-meta">
                <h4>Wide Receiver Slot</h4>
                <p>Awaiting roster</p>
            </div>
            <div class="player-score">0.0</div>
        </div>
        <div class="roster-row">
            <div class="pos-pill">TE</div>
            <div class="player-meta">
                <h4>Tight End Slot</h4>
                <p>Awaiting roster</p>
            </div>
            <div class="player-score">0.0</div>
        </div>
        <div class="roster-row">
            <div class="pos-pill">FLX</div>
            <div class="player-meta">
                <h4>Flex Slot</h4>
                <p>Awaiting roster</p>
            </div>
            <div class="player-score">0.0</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
