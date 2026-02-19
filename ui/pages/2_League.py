import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import random
import time

import altair as alt
import pandas as pd
import streamlit as st

from ui.lib.components.league import render_league_header, render_league_tabs
from ui.lib.components.matchup import matchup_summary_html, team_lineup_html
from ui.lib.components.sidebar import render_sidebar_nav
from ui.lib.components.top_nav import render_top_nav
from ui.lib.components.teams import render_team_card
from ui.lib.components.transactions import transactions_feed_html
from ui.lib.mock.draft import generate_draft_state
from ui.lib.mock.league import generate_league_data
from ui.lib.mock.matchup import generate_matchup_data
from ui.lib.mock.news import generate_league_news
from ui.lib.mock.players import generate_players_data
from ui.lib.mock.public import public_id_for_league
from ui.lib.mock.schedule import generate_schedule
from ui.lib.mock.team import generate_team_data
from ui.lib.mock.trades import generate_trades
from ui.lib.mock.transactions import generate_transactions
from ui.lib.mock.waivers import generate_waivers
from ui.lib.theme import apply_theme
from ui.lib.team_branding import team_logo_html

st.set_page_config(page_title="League", layout="wide")
apply_theme()
render_sidebar_nav("league")

st.markdown(
    """
    <style>
    .league-shell {
        max-width: 1200px;
        margin: 0 auto;
        padding-bottom: 2rem;
    }

    .commissioner-pill {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid rgba(74, 163, 255, 0.4);
        background: rgba(74, 163, 255, 0.15);
        color: #8fb9ff;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-weight: 700;
        justify-content: center;
        min-width: 120px;
    }

    .commissioner-pill.neutral {
        border-color: rgba(160, 170, 190, 0.4);
        background: rgba(160, 170, 190, 0.15);
        color: #a7b4c7;
    }

    div[data-testid="stRadio"] > div {
        background: #121820;
        border-radius: 999px;
        padding: 4px;
        border: 1px solid rgba(255, 255, 255, 0.06);
    }

    div[data-testid="stRadio"] label {
        margin: 0 4px;
    }

    div[data-testid="stRadio"] label > div:first-child {
        display: none;
    }

    div[data-testid="stRadio"] label > div:last-child {
        background: transparent;
        border-radius: 999px;
        padding: 6px 12px;
        font-size: 0.72rem;
        letter-spacing: 0.08rem;
        text-transform: uppercase;
        font-weight: 700;
        color: #9fb0c7;
    }

    div[data-testid="stRadio"] label[data-selected="true"] > div:last-child {
        background: #203044;
        color: #f3f6ff;
    }

    .matchup-summary {
        display: grid;
        grid-template-columns: 1fr 1.5fr 1fr;
        gap: 1rem;
        align-items: center;
        background: linear-gradient(150deg, #121820 0%, #0f141c 100%);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 1.2rem;
    }

    .matchup-team {
        text-align: center;
    }

    .matchup-name {
        font-weight: 700;
        font-size: 1rem;
        color: #f3f6ff;
    }

    .matchup-record {
        font-size: 0.75rem;
        color: #92a0b6;
        margin-bottom: 0.3rem;
    }

    .matchup-score {
        font-size: 1.5rem;
        font-weight: 800;
        color: #f3f6ff;
    }

    .matchup-proj {
        font-size: 0.75rem;
        color: #9fb0c7;
    }

    .matchup-center {
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        align-items: center;
    }

    .matchup-status {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
    }

    .win-prob {
        width: 100%;
        max-width: 320px;
    }

    .win-prob__bar {
        display: flex;
        height: 10px;
        border-radius: 999px;
        overflow: hidden;
        background: rgba(255, 255, 255, 0.06);
    }

    .win-prob__away {
        background: #4aa3ff;
    }

    .win-prob__home {
        background: #42d17c;
    }

    .win-prob__labels {
        display: flex;
        justify-content: space-between;
        font-size: 0.7rem;
        color: #a5b2c7;
        margin-top: 0.25rem;
    }

    .win-prob__caption {
        text-align: center;
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #7f8da3;
        margin-top: 0.35rem;
    }

    .team-lineup {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
    }

    .team-lineup__header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.6rem;
    }

    .team-lineup__name {
        font-weight: 700;
        color: #f3f6ff;
    }

    .team-lineup__record {
        font-size: 0.75rem;
        color: #92a0b6;
    }

    .lineup-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin: 0.6rem 0 0.3rem;
    }

    .lineup-table {
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
        font-size: 0.75rem;
    }

    .lineup-row {
        display: grid;
        grid-template-columns: 2.2fr 0.6fr 0.6fr 0.7fr 0.9fr 1.6fr;
        gap: 0.4rem;
        align-items: center;
        padding: 0.3rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    .lineup-row:last-child {
        border-bottom: none;
    }

    .lineup-header {
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-size: 0.62rem;
        color: #7f8da3;
    }

    .lineup-player {
        display: flex;
        flex-direction: column;
    }

    .lineup-name {
        color: #f3f6ff;
        font-weight: 600;
    }

    .lineup-sub {
        color: #8796ac;
        font-size: 0.65rem;
    }

    .lineup-stat {
        font-weight: 700;
        color: #e7f0ff;
    }

    .lineup-status {
        color: #9fb0c7;
        font-size: 0.65rem;
    }

    .lineup-stats {
        color: #9aa7bb;
        font-size: 0.65rem;
    }

    .standings-table {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
        font-size: 0.78rem;
    }

    .standings-row {
        display: grid;
        grid-template-columns: 2.2fr 0.8fr 0.8fr 0.8fr 0.7fr 0.6fr;
        gap: 0.5rem;
        align-items: center;
        padding: 0.35rem 0.3rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .standings-row:last-child {
        border-bottom: none;
    }

    .standings-header {
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-size: 0.62rem;
        color: #7f8da3;
        padding-top: 0.2rem;
    }

    .standings-team {
        font-weight: 600;
        color: #f3f6ff;
    }

    .sort-pill {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 999px;
        padding: 0.2rem 0.6rem;
        font-size: 0.65rem;
        letter-spacing: 0.08rem;
        text-transform: uppercase;
        color: #a5b2c7;
        margin-right: 0.35rem;
    }

    .sort-pill.active {
        border-color: rgba(74, 163, 255, 0.6);
        color: #cfe1ff;
        background: rgba(74, 163, 255, 0.2);
    }

    .playoff-shell {
        margin-top: 1.2rem;
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
    }

    .playoff-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }

    .playoff-bracket {
        display: grid;
        grid-template-columns: 1fr 0.6fr 1fr;
        gap: 0.8rem;
        align-items: center;
    }

    .playoff-slot {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 0.45rem 0.6rem;
        font-size: 0.78rem;
        font-weight: 600;
        color: #f3f6ff;
    }

    .playoff-connector {
        height: 1px;
        background: rgba(255, 255, 255, 0.2);
        margin: 0.4rem 0;
    }

    .teams-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.8rem;
        margin-top: 0.8rem;
    }

    .team-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
        min-height: 150px;
    }

    .team-card__header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.4rem;
    }

    .team-card__name {
        font-weight: 700;
        color: #f3f6ff;
    }

    .team-card__record {
        font-size: 0.75rem;
        color: #9fb0c7;
    }

    .team-card__owner {
        font-size: 0.75rem;
        color: #8fa0b6;
    }

    .team-card__meta {
        display: flex;
        justify-content: space-between;
        font-size: 0.72rem;
        color: #a5b2c7;
    }

    .team-card__link {
        margin-top: auto;
        text-decoration: none;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fb9ff;
    }

    .players-shell {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
        margin-top: 0.6rem;
    }

    .players-table {
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
        font-size: 0.75rem;
    }

    .players-row {
        display: grid;
        grid-template-columns: 2fr 0.6fr 1fr 0.6fr 0.6fr 0.6fr 0.7fr 0.7fr;
        gap: 0.4rem;
        align-items: center;
        padding: 0.3rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .players-row:last-child {
        border-bottom: none;
    }

    .players-header {
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-size: 0.62rem;
        color: #7f8da3;
    }

    .players-name {
        font-weight: 600;
        color: #f3f6ff;
    }

    .players-sub {
        color: #8fa0b6;
        font-size: 0.65rem;
    }

    .players-availability {
        font-weight: 700;
        color: #42d17c;
    }

    .players-availability.owned {
        color: #f0b84c;
    }

    .players-view button {
        background: #203044;
        border: 1px solid rgba(255, 255, 255, 0.15);
        color: #d7e6ff;
        border-radius: 999px;
        padding: 4px 10px;
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
    }

    .news-shell {
        display: grid;
        grid-template-columns: 1.2fr 1fr;
        gap: 1rem;
        margin-top: 0.8rem;
    }

    .news-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
    }

    .news-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }

    .news-item {
        padding: 0.4rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .news-item:last-child {
        border-bottom: none;
    }

    .news-item h4 {
        margin: 0;
        font-size: 0.88rem;
        color: #f3f6ff;
    }

    .news-item p {
        margin: 0.2rem 0 0.1rem;
        font-size: 0.74rem;
        color: #9aa7bb;
    }

    .news-item span {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #7f8da3;
    }

    .transactions-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
        margin-top: 0.8rem;
    }

    .transactions-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }

    .transactions-feed {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
        font-size: 0.78rem;
    }

    .transaction-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.8rem;
        padding: 0.4rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .transaction-row:last-child {
        border-bottom: none;
    }

    .transaction-left {
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }

    .transaction-badge {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: rgba(74, 163, 255, 0.18);
        border: 1px solid rgba(74, 163, 255, 0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.7rem;
        color: #cfe1ff;
    }

    .transaction-detail {
        font-weight: 600;
        color: #f3f6ff;
    }

    .transaction-type {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
    }

    .transaction-meta {
        font-size: 0.65rem;
        color: #9aa7bb;
    }

    .transaction-time {
        font-size: 0.7rem;
        color: #9aa7bb;
        white-space: nowrap;
    }

    .draft-shell {
        display: grid;
        grid-template-columns: 1.3fr 1fr;
        gap: 1rem;
        margin-top: 0.8rem;
    }

    .draft-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
    }

    .draft-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }

    .draft-row {
        display: grid;
        grid-template-columns: 1.6fr 0.6fr 1fr 0.6fr;
        gap: 0.4rem;
        align-items: center;
        padding: 0.3rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        font-size: 0.75rem;
    }

    .draft-row:last-child {
        border-bottom: none;
    }

    .draft-header {
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-size: 0.62rem;
        color: #7f8da3;
    }

    .draft-pick-line {
        display: flex;
        justify-content: space-between;
        font-size: 0.8rem;
        padding: 0.35rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .draft-pick-line:last-child {
        border-bottom: none;
    }

    .draft-pill {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid rgba(74, 163, 255, 0.4);
        background: rgba(74, 163, 255, 0.15);
        color: #8fb9ff;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-weight: 700;
    }

    .draft-pill.live {
        border-color: rgba(66, 209, 124, 0.5);
        background: rgba(66, 209, 124, 0.2);
        color: #b8f1d0;
    }

    .schedule-shell {
        display: flex;
        flex-direction: column;
        gap: 0.6rem;
        margin-top: 0.8rem;
    }

    .schedule-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .schedule-row {
        display: grid;
        grid-template-columns: 1fr 0.6fr 0.8fr;
        gap: 0.4rem;
        align-items: center;
        font-size: 0.8rem;
        padding: 0.2rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .schedule-row:last-child {
        border-bottom: none;
    }

    .schedule-team {
        font-weight: 600;
        color: #f3f6ff;
    }

    .schedule-score {
        font-weight: 700;
        color: #e7f0ff;
        text-align: right;
    }

    .schedule-proj {
        font-size: 0.7rem;
        color: #8fa0b6;
        text-align: right;
    }

    .schedule-winner {
        color: #42d17c;
    }

    .schedule-grid {
        margin-top: 0.8rem;
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        overflow: hidden;
    }

    .schedule-grid table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.72rem;
    }

    .schedule-grid th,
    .schedule-grid td {
        padding: 0.35rem 0.4rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        border-right: 1px solid rgba(255, 255, 255, 0.06);
        text-align: left;
        color: #c7d5ea;
    }

    .schedule-grid th {
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-size: 0.6rem;
        color: #7f8da3;
        background: rgba(255, 255, 255, 0.02);
    }

    .schedule-grid td:last-child,
    .schedule-grid th:last-child {
        border-right: none;
    }

    .ticker-shell {
        background: rgba(18, 24, 32, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        overflow: hidden;
        margin: 0.6rem 0 0.2rem;
    }

    .ticker-track {
        display: flex;
        gap: 2rem;
        padding: 0.4rem 0.8rem;
        animation: ticker 20s linear infinite;
        white-space: nowrap;
        color: #9fb0c7;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
    }

    .ticker-item {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
    }

    @keyframes ticker {
        0% { transform: translateX(0); }
        100% { transform: translateX(-50%); }
    }

    .injury-filters {
        display: flex;
        gap: 0.6rem;
        flex-wrap: wrap;
        margin-bottom: 0.6rem;
    }

    .myteam-shell {
        display: grid;
        grid-template-columns: 2.2fr 1fr;
        gap: 1rem;
        margin-top: 0.8rem;
    }

    .myteam-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
        margin-bottom: 1rem;
    }

    .myteam-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }

    .myteam-row {
        display: grid;
        grid-template-columns: 1.6fr 0.6fr 0.6fr 0.6fr;
        gap: 0.4rem;
        align-items: center;
        font-size: 0.75rem;
        padding: 0.3rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .myteam-row:last-child {
        border-bottom: none;
    }

    .myteam-header {
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-size: 0.62rem;
        color: #7f8da3;
    }

    .trade-shell {
        display: grid;
        grid-template-columns: 1.2fr 1fr;
        gap: 1rem;
        margin-top: 0.8rem;
    }

    .trade-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
    }

    .trade-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }

    .trade-row {
        padding: 0.5rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        font-size: 0.78rem;
    }

    .trade-row:last-child {
        border-bottom: none;
    }

    .trade-status {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #9aa7bb;
    }

    .trade-actions button {
        margin-right: 0.4rem;
    }

    .waiver-shell {
        display: grid;
        grid-template-columns: 1.2fr 1fr;
        gap: 1rem;
        margin-top: 0.8rem;
    }

    .waiver-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 0.8rem;
    }

    .waiver-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }

    .waiver-row {
        display: grid;
        grid-template-columns: 1.6fr 0.6fr 0.6fr;
        gap: 0.4rem;
        align-items: center;
        font-size: 0.78rem;
        padding: 0.35rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .waiver-row:last-child {
        border-bottom: none;
    }

    .waiver-header {
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        font-size: 0.62rem;
        color: #7f8da3;
    }

    .claim-row {
        display: grid;
        grid-template-columns: 0.5fr 1.4fr 1.4fr 0.6fr;
        gap: 0.4rem;
        align-items: center;
        font-size: 0.76rem;
        padding: 0.35rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }

    .claim-row:last-child {
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


def _set_query_params(params: dict) -> None:
    if hasattr(st, "query_params"):
        for key, value in params.items():
            st.query_params[key] = value
    else:
        st.experimental_set_query_params(**params)


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


def _toast(message: str) -> None:
    if hasattr(st, "toast"):
        st.toast(message)
    else:
        st.success(message)


params = _get_query_params()
league_id_param = params.get("leagueId") or params.get("league")
if isinstance(league_id_param, list):
    league_id_param = league_id_param[0] if league_id_param else None

league_id = st.session_state.get("selected_league_id")
if league_id is None and league_id_param:
    try:
        league_id = int(league_id_param)
    except ValueError:
        league_id = None

if league_id is None:
    st.info("Select a league from the Leagues page to continue.")
    st.stop()

st.session_state["selected_league_id"] = league_id

league_state_key = f"league_state_{league_id}"
if league_state_key not in st.session_state:
    st.session_state[league_state_key] = generate_league_data(league_id)["league"]
league = st.session_state[league_state_key]

draft_status_key = f"draft_status_{league_id}"
if draft_status_key not in st.session_state:
    st.session_state[draft_status_key] = league["draft"]["status"]
draft_status = st.session_state[draft_status_key]
league["draft"]["status"] = draft_status
draft_enabled = draft_status in {"scheduled", "live"}
playoff_seeds_key = f"playoff_seeds_{league_id}"

tabs = [
    "Matchup",
    "My Team",
    "Standings",
    "Teams",
    "Players",
    "League News",
    "Transactions",
    "Trade Center",
    "Waivers",
    "Schedule",
    "Settings",
]
if draft_enabled:
    tabs.insert(6, "Draft Center")
tab_param = params.get("tab")
if isinstance(tab_param, list):
    tab_param = tab_param[0] if tab_param else None
nav_target_tab = st.session_state.pop("nav_target_tab", None)
if nav_target_tab in tabs:
    active_tab = nav_target_tab
else:
    active_tab = tab_param if tab_param in tabs else "Matchup"

if league_id_param != str(league_id) or tab_param != active_tab:
    _set_query_params({"leagueId": str(league_id), "tab": active_tab})

nav_current = "league"
if active_tab == "Matchup":
    nav_current = "matchup"
elif active_tab == "My Team":
    nav_current = "team"
elif active_tab == "Schedule":
    nav_current = "scoreboard"
elif active_tab == "Players":
    nav_current = "players"
render_top_nav(nav_current)

st.markdown('<div class="league-shell">', unsafe_allow_html=True)

week_options = list(range(1, 16))
selected_week = render_league_header(league, league["current_week"], week_options)
selected_tab = render_league_tabs(tabs, active_tab)

if selected_tab != active_tab:
    _set_query_params({"leagueId": str(league_id), "tab": selected_tab})
    st.stop()

public_id = public_id_for_league(league_id)
share_key = f"public_url_{league_id}"
share_col_left, share_col_right = st.columns([3, 1])
with share_col_right:
    if st.button("Share"):
        st.session_state[share_key] = f"/Public_League?publicId={public_id}"
if share_key in st.session_state:
    st.text_input("Public URL", value=st.session_state[share_key], disabled=True)

activity_key = f"activity_{league_id}"
if activity_key not in st.session_state:
    st.session_state[activity_key] = generate_transactions(league)
activity_items = st.session_state[activity_key][:8]
if activity_items:
    ticker_items = []
    for item in activity_items:
        ticker_items.append(
            f"<div class='ticker-item'>{team_logo_html(item['team'])} {item['detail']}</div>"
        )
    ticker_html = "".join(ticker_items)
    st.markdown(
        f"""
        <div class="ticker-shell">
            <div class="ticker-track">{ticker_html}{ticker_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

if selected_tab == "Matchup":
    matchup = generate_matchup_data(league, selected_week)
    st.markdown(matchup_summary_html(matchup), unsafe_allow_html=True)

    trend_df = pd.DataFrame(matchup["trend"])
    win_prob_df = trend_df.melt(
        id_vars=["label"],
        value_vars=["away_win", "home_win"],
        var_name="team",
        value_name="win_prob",
    )
    win_prob_df["team"] = win_prob_df["team"].map(
        {"away_win": matchup["away"]["name"], "home_win": matchup["home"]["name"]}
    )
    proj_df = trend_df.melt(
        id_vars=["label"],
        value_vars=["away_proj", "home_proj"],
        var_name="team",
        value_name="projection",
    )
    proj_df["team"] = proj_df["team"].map(
        {"away_proj": matchup["away"]["name"], "home_proj": matchup["home"]["name"]}
    )
    win_chart = (
        alt.Chart(win_prob_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("label:N", title="Time"),
            y=alt.Y("win_prob:Q", title="Win Probability"),
            color=alt.Color("team:N", legend=None),
            tooltip=["label", "team", "win_prob"],
        )
        .properties(height=180)
    )
    proj_chart = (
        alt.Chart(proj_df)
        .mark_line(point=True)
        .encode(
            x=alt.X("label:N", title="Time"),
            y=alt.Y("projection:Q", title="Projection"),
            color=alt.Color("team:N", legend=None),
            tooltip=["label", "team", "projection"],
        )
        .properties(height=180)
    )
    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown("**Win Probability Trend**")
        st.altair_chart(win_chart, use_container_width=True)
    with chart_right:
        st.markdown("**Projection Trend**")
        st.altair_chart(proj_chart, use_container_width=True)

    position_tabs = ["All", "QB", "RB", "WR", "TE", "FLEX", "K", "DST"]
    tab_objects = st.tabs(position_tabs)

    def _filter_team(team: dict, position: str) -> dict:
        lineup = team["lineup"]
        if position == "All":
            return team
        positions = {position}
        if position == "FLEX":
            positions = {"RB", "WR", "TE"}
        starters = [player for player in lineup["starters"] if player["pos"] in positions]
        bench = [player for player in lineup["bench"] if player["pos"] in positions]
        filtered_lineup = {
            "starters": starters,
            "bench": bench,
            "total_points": lineup["total_points"],
            "total_proj": lineup["total_proj"],
        }
        return {"name": team["name"], "record": team["record"], "lineup": filtered_lineup}

    for tab, label in zip(tab_objects, position_tabs):
        with tab:
            away_col, home_col = st.columns(2)
            with away_col:
                st.markdown(team_lineup_html(_filter_team(matchup["away"], label)), unsafe_allow_html=True)
            with home_col:
                st.markdown(team_lineup_html(_filter_team(matchup["home"], label)), unsafe_allow_html=True)
elif selected_tab == "Standings":
    sort_options = [
        ("Rank", "rank"),
        ("PF", "points_for"),
        ("PA", "points_against"),
        ("Streak", "streak"),
    ]
    sort_labels = [label for label, _ in sort_options]
    sort_values = [value for _, value in sort_options]
    sort_selection = st.selectbox("Sort by", sort_labels, index=0)
    sort_key = sort_values[sort_labels.index(sort_selection)]
    sort_desc = st.toggle("Descending", value=True)

    teams = league["teams"]

    def _sort_key(team: dict) -> tuple:
        if sort_key == "rank":
            return (team["wins"], -(team["losses"] + team["ties"]))
        if sort_key == "streak":
            return (team["streak"][0], int(team["streak"][1:]))
        return team.get(sort_key, 0)

    playoff_override = st.session_state.get(playoff_seeds_key, [])
    if sort_key == "rank" and playoff_override:
        seed_lookup = {name: idx for idx, name in enumerate(playoff_override)}
        seeded = [team for name in playoff_override for team in teams if team["name"] == name]
        remaining = [team for team in teams if team["name"] not in seed_lookup]
        remaining_sorted = sorted(remaining, key=_sort_key, reverse=True)
        sorted_teams = seeded + remaining_sorted
    else:
        sorted_teams = sorted(teams, key=_sort_key, reverse=sort_desc)
    standings = []
    for idx, team in enumerate(sorted_teams, start=1):
        standings.append(
            {
                "rank": idx,
                "team": team["name"],
                "record": f"{team['wins']}-{team['losses']}-{team['ties']}",
                "points_for": team["points_for"],
                "points_against": team["points_against"],
                "streak": team["streak"],
            }
        )

    st.markdown(
        f"""
        <div>
            <span class="sort-pill active">Sort: {sort_selection}</span>
            <span class="sort-pill">{'Desc' if sort_desc else 'Asc'}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    header = (
        '<div class="standings-row standings-header">'
        "<div>Team</div>"
        "<div>W-L-T</div>"
        "<div>PF</div>"
        "<div>PA</div>"
        "<div>Streak</div>"
        "<div>Rank</div>"
        "</div>"
    )
    rows = []
    for entry in standings:
        rows.append(
            f"""
            <div class="standings-row">
                <div class="standings-team">{team_logo_html(entry['team'])} {entry['team']}</div>
                <div>{entry['record']}</div>
                <div>{entry['points_for']}</div>
                <div>{entry['points_against']}</div>
                <div>{entry['streak']}</div>
                <div>#{entry['rank']}</div>
            </div>
            """
        )
    st.markdown(f'<div class="standings-table">{header}{"".join(rows)}</div>', unsafe_allow_html=True)

    playoff_seeds = standings[:4]
    if playoff_seeds:
        seed_one = playoff_seeds[0]["team"]
        seed_two = playoff_seeds[1]["team"]
        seed_three = playoff_seeds[2]["team"] if len(playoff_seeds) > 2 else "TBD"
        seed_four = playoff_seeds[3]["team"] if len(playoff_seeds) > 3 else "TBD"
        st.markdown(
            f"""
            <div class="playoff-shell">
                <div class="playoff-title">Playoff Bracket Preview</div>
                <div class="playoff-bracket">
                    <div>
                        <div class="playoff-slot">1. {team_logo_html(seed_one)} {seed_one}</div>
                        <div class="playoff-connector"></div>
                        <div class="playoff-slot">4. {team_logo_html(seed_four)} {seed_four}</div>
                    </div>
                    <div></div>
                    <div>
                        <div class="playoff-slot">2. {team_logo_html(seed_two)} {seed_two}</div>
                        <div class="playoff-connector"></div>
                        <div class="playoff-slot">3. {team_logo_html(seed_three)} {seed_three}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
elif selected_tab == "Teams":
    st.subheader("Teams")

    def _view_team(team_id: int) -> None:
        st.session_state["selected_league_id"] = league_id
        st.session_state["selected_team_id"] = team_id
        if hasattr(st, "switch_page"):
            st.switch_page("pages/3_Team.py")
        else:
            st.info("Open the Team page from the sidebar to continue.")

    columns = st.columns(3)
    for index, team in enumerate(league["teams"]):
        with columns[index % 3]:
            render_team_card(league_id, team, _view_team)
elif selected_tab == "My Team":
    user_team_id = league.get("user_team_id") or (league["teams"][0]["id"] if league["teams"] else None)
    if user_team_id is None:
        st.info("No team found for this league.")
    else:
        st.session_state["selected_team_id"] = user_team_id
        team = next((item for item in league["teams"] if item["id"] == user_team_id), None)
        if team is None:
            st.info("Team not found.")
        else:
            team_data = generate_team_data(league, team)
            st.subheader(f"My Team: {team['name']}")
            st.caption(f"{team['record']} · {team['owner']}")

            main_col, side_col = st.columns([2.2, 1])
            with main_col:
                roster = team_data["roster"]
                for title, rows in [("Starters", roster["starters"]), ("Bench", roster["bench"])]:
                    header = (
                        '<div class="myteam-row myteam-header">'
                        "<div>Player</div><div>Pos</div><div>Pts</div><div>Proj</div></div>"
                    )
                    body = "".join(
                        f"<div class='myteam-row'><div>{player['name']}</div><div>{player['pos']}</div>"
                        f"<div>{player['points']}</div><div>{player['proj']}</div></div>"
                        for player in rows
                    )
                    st.markdown(
                        f'<div class="myteam-card"><div class="myteam-title">{title}</div>{header}{body}</div>',
                        unsafe_allow_html=True,
                    )

                perf = team_data["recent_performance"]
                st.markdown(
                    '<div class="myteam-card"><div class="myteam-title">Recent Performance</div>',
                    unsafe_allow_html=True,
                )
                if perf:
                    st.line_chart([item["points"] for item in perf], height=160)
                else:
                    st.caption("No recent performance data.")
                st.markdown("</div>", unsafe_allow_html=True)

            with side_col:
                schedule = team_data["schedule"]
                schedule_rows = "".join(
                    f"<div class='myteam-row'><div>Week {item['week']} vs {item['opponent']}</div>"
                    f"<div></div><div></div><div>{item['projection']} proj</div></div>"
                    for item in schedule
                )
                st.markdown(
                    f'<div class="myteam-card"><div class="myteam-title">Upcoming</div>{schedule_rows}</div>',
                    unsafe_allow_html=True,
                )

                transactions = team_data["transactions"]
                transactions_rows = "".join(
                    f"<div class='myteam-row'><div>{item['detail']}</div><div></div><div></div><div>{item['time']}</div></div>"
                    for item in transactions
                )
                st.markdown(
                    f'<div class="myteam-card"><div class="myteam-title">Recent Moves</div>{transactions_rows}</div>',
                    unsafe_allow_html=True,
                )

                if st.button("Open full team page"):
                    if hasattr(st, "switch_page"):
                        st.switch_page("pages/3_Team.py")
elif selected_tab == "Players":
    st.subheader("Players")

    seed_key = f"players_seed_{league_id}"
    if seed_key not in st.session_state:
        st.session_state[seed_key] = str(time.time_ns())
    players_seed = st.session_state[seed_key]

    @st.cache_data(show_spinner=False)
    def _get_players(seed: str) -> dict:
        return generate_players_data(seed, count=240)

    @st.cache_data(show_spinner=False)
    def _filter_sort_players(
        seed: str,
        position: str,
        team: str,
        availability: str,
        search: str,
        sort_key: str,
        sort_desc: bool,
    ) -> list[dict]:
        data = _get_players(seed)
        players = data["players"]
        search_normalized = search.strip().lower()

        filtered = []
        for player in players:
            if position != "ALL" and player["pos"] != position:
                continue
            if team != "ALL" and player["team"] != team:
                continue
            if availability != "ALL" and player["availability"] != availability:
                continue
            if search_normalized and search_normalized not in player["name"].lower():
                continue
            filtered.append(player)

        filtered.sort(key=lambda item: item.get(sort_key, 0), reverse=sort_desc)
        return filtered

    data = _get_players(players_seed)
    team_options = ["ALL"] + data["teams"]

    filter_left, filter_mid, filter_right, filter_sort = st.columns([1.2, 1.2, 1.2, 1])
    with filter_left:
        position_choice = st.selectbox("Position", ["ALL", "QB", "RB", "WR", "TE", "K"])
    with filter_mid:
        team_choice = st.selectbox("Team", team_options)
    with filter_right:
        availability_choice = st.selectbox("Availability", ["ALL", "FA", "Owned"])
    with filter_sort:
        sort_choice = st.selectbox("Sort", ["Proj", "Last", "Avg", "Owned%"])
        sort_desc = st.toggle("Desc", value=True)

    search_query = st.text_input("Search")

    sort_map = {"Proj": "proj", "Last": "last", "Avg": "avg", "Owned%": "owned_pct"}
    filtered_players = _filter_sort_players(
        players_seed,
        position_choice,
        team_choice,
        availability_choice,
        search_query,
        sort_map[sort_choice],
        sort_desc,
    )

    if not filtered_players:
        st.info("No players match those filters.")
    else:
        header = (
            '<div class="players-row players-header">'
            "<div>Player</div>"
            "<div>Pos</div>"
            "<div>Team</div>"
            "<div>Proj</div>"
            "<div>Last</div>"
            "<div>Avg</div>"
            "<div>Owned%</div>"
            "<div></div>"
            "</div>"
        )
        st.markdown(f'<div class="players-shell"><div class="players-table">{header}', unsafe_allow_html=True)
        for player in filtered_players:
            availability_class = "owned" if player["availability"] == "Owned" else ""
            row_left, row_pos, row_team, row_proj, row_last, row_avg, row_owned, row_action = st.columns(
                [2, 0.6, 1, 0.6, 0.6, 0.6, 0.7, 0.7]
            )
            row_left.markdown(
                f"<div class='players-name'>{player['name']}<div class='players-sub'>{player['availability']}</div></div>",
                unsafe_allow_html=True,
            )
            row_pos.write(player["pos"])
            row_team.markdown(
                f"{player['team']}<div class='players-sub'>{player['conf']}</div>",
                unsafe_allow_html=True,
            )
            row_proj.write(player["proj"])
            row_last.write(player["last"])
            row_avg.write(player["avg"])
            row_owned.markdown(
                f"<span class='players-availability {availability_class}'>{player['owned_pct']}</span>",
                unsafe_allow_html=True,
            )
            with row_action:
                st.markdown("<div class='players-view'>", unsafe_allow_html=True)
                if st.button("View", key=f"player_view_{player['id']}"):
                    st.session_state["selected_player_id"] = player["id"]
                    st.session_state["selected_player"] = player
                    if hasattr(st, "switch_page"):
                        st.switch_page("pages/4_Player.py")
                    else:
                        st.info("Open the Player page from the sidebar to continue.")
                st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)
elif selected_tab == "League News":
    st.subheader("League News")
    news = generate_league_news(league)
    status_options = ["All", "Questionable", "Doubtful", "Out", "Probable"]
    position_options = ["All", "QB", "RB", "WR", "TE", "K"]
    team_options = ["All"] + sorted({injury["team"] for injury in news["injuries"]})
    filter_left, filter_mid, filter_right = st.columns(3)
    with filter_left:
        status_filter = st.selectbox("Status", status_options)
    with filter_mid:
        pos_filter = st.selectbox("Position", position_options)
    with filter_right:
        team_filter = st.selectbox("Team", team_options)

    injuries_filtered = []
    for injury in news["injuries"]:
        if status_filter != "All" and injury["status"] != status_filter:
            continue
        if pos_filter != "All" and injury["pos"] != pos_filter:
            continue
        if team_filter != "All" and injury["team"] != team_filter:
            continue
        injuries_filtered.append(injury)

    headlines_html = "".join(
        f"<div class='news-item'><h4>{item['title']}</h4><p>{item['summary']}</p><span>{item['time']}</span></div>"
        for item in news["headlines"]
    )
    previews_html = "".join(
        f"<div class='news-item'><h4>{item['title']}</h4><p>{item['summary']}</p></div>"
        for item in news["previews"]
    )
    injuries_html = "".join(
        f"<div class='news-item'><h4>{item['player']} · {item['team']} · {item['pos']}</h4><p>{item['status']} · Impact {item['impact']}</p></div>"
        for item in injuries_filtered
    )
    st.markdown(
        f"""
        <div class="news-shell">
            <div class="news-card">
                <div class="news-title">Headlines</div>
                {headlines_html}
            </div>
            <div class="news-card">
                <div class="news-title">Matchup Previews</div>
                {previews_html}
            </div>
            <div class="news-card">
                <div class="news-title">Injury Center</div>
                {injuries_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
elif selected_tab == "Draft Center":
    st.subheader("Draft Center")
    draft_state_key = f"draft_state_{league_id}"
    if draft_state_key not in st.session_state:
        st.session_state[draft_state_key] = generate_draft_state(league)
    draft_state = st.session_state[draft_state_key]

    status_class = "live" if draft_status == "live" else ""
    st.markdown(
        f'<div class="draft-pill {status_class}">Status: {draft_status.title()}</div>',
        unsafe_allow_html=True,
    )

    if draft_status == "scheduled":
        if st.button("Start Draft"):
            st.session_state[draft_status_key] = "live"
            draft_status = "live"
    total_picks = draft_state["rounds"] * len(draft_state["order"])
    pick_index = len(draft_state["picks"])
    if pick_index >= total_picks:
        st.session_state[draft_status_key] = "complete"
        draft_status = "complete"
        st.success("Draft complete.")

    if draft_status == "live":
        team_on_clock = draft_state["order"][pick_index % len(draft_state["order"])]
        round_number = (pick_index // len(draft_state["order"])) + 1
        st.caption(f"Round {round_number} · Pick {pick_index + 1} · {team_on_clock['name']} on the clock")

        if st.button("Auto-pick"):
            if draft_state["available"]:
                best_player = draft_state["available"].pop(0)
                draft_state["picks"].append(
                    {
                        "round": round_number,
                        "overall": pick_index + 1,
                        "team": team_on_clock["name"],
                        "player": best_player["name"],
                        "pos": best_player["pos"],
                        "proj": best_player["proj"],
                    }
                )
                st.session_state[draft_state_key] = draft_state

        if st.button("Reset Draft"):
            st.session_state[draft_state_key] = generate_draft_state(league)

    left_col, right_col = st.columns(2)
    with left_col:
        available = draft_state["available"][:12]
        header = (
            '<div class="draft-row draft-header">'
            "<div>Player</div><div>Pos</div><div>Team</div><div>Proj</div></div>"
        )
        rows = []
        for player in available:
            rows.append(
                f"""
                <div class="draft-row">
                    <div>{player['name']}</div>
                    <div>{player['pos']}</div>
                    <div>{player['team']}</div>
                    <div>{player['proj']}</div>
                </div>
                """
            )
        st.markdown(
            f'<div class="draft-card"><div class="draft-title">Available Players</div>{header}{"".join(rows)}</div>',
            unsafe_allow_html=True,
        )
    with right_col:
        picks = draft_state["picks"][-10:]
        picks_html = "".join(
            f"<div class='draft-pick-line'><span>R{pick['round']} · {pick['team']}</span><span>{pick['player']} ({pick['pos']})</span></div>"
            for pick in picks
        )
        st.markdown(
            f"""
            <div class="draft-card">
                <div class="draft-title">Recent Picks</div>
                {picks_html if picks_html else "<div class='draft-pick-line'>No picks yet.</div>"}
            </div>
            """,
            unsafe_allow_html=True,
        )
elif selected_tab == "Transactions":
    st.subheader("Transactions")
    transactions_key = f"transactions_{league_id}"
    if transactions_key not in st.session_state:
        st.session_state[transactions_key] = generate_transactions(league)
    transactions = st.session_state[transactions_key]
    st.markdown(
        f"""
        <div class="transactions-card">
            <div class="transactions-title">Recent Activity</div>
            {transactions_feed_html(transactions)}
        </div>
        """,
        unsafe_allow_html=True,
    )
elif selected_tab == "Trade Center":
    st.subheader("Trade Center")
    trade_state_key = f"trade_state_{league_id}"
    if trade_state_key not in st.session_state:
        st.session_state[trade_state_key] = generate_trades(league)
    trade_state = st.session_state[trade_state_key]

    players_seed_key = f"players_seed_{league_id}"
    if players_seed_key not in st.session_state:
        st.session_state[players_seed_key] = str(time.time_ns())
    trade_players = generate_players_data(st.session_state[players_seed_key], count=120)["players"]
    player_names = [player["name"] for player in trade_players]

    with st.form("trade_proposal"):
        trade_left, trade_right = st.columns(2)
        with trade_left:
            team_a = st.selectbox("Team A", [team["name"] for team in league["teams"]], key="trade_team_a")
            give_a = st.multiselect("Team A gives", player_names, max_selections=3)
        with trade_right:
            team_b = st.selectbox("Team B", [team["name"] for team in league["teams"]], key="trade_team_b")
            give_b = st.multiselect("Team B gives", player_names, max_selections=3)
        submitted = st.form_submit_button("Propose Trade")

    if submitted and team_a != team_b and give_a and give_b:
        new_offer = {
            "id": int(time.time()),
            "from": team_a,
            "to": team_b,
            "give": give_a,
            "receive": give_b,
            "status": "Pending",
        }
        trade_state["offers"].insert(0, new_offer)
        st.session_state[trade_state_key] = trade_state
        st.success("Trade proposal submitted.")
    elif submitted:
        st.error("Select two different teams and at least one player each.")

    offers = trade_state["offers"]
    history = trade_state["history"]

    left_col, right_col = st.columns(2)
    with left_col:
        st.markdown('<div class="trade-card"><div class="trade-title">Pending Offers</div>', unsafe_allow_html=True)
        if not offers:
            st.caption("No pending offers.")
        for offer in list(offers):
            st.markdown(
                f"""
                <div class="trade-row">
                    <div><strong>{offer['from']}</strong> gives {", ".join(offer['give'])}</div>
                    <div><strong>{offer['to']}</strong> gives {", ".join(offer['receive'])}</div>
                    <div class="trade-status">{offer['status']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            action_col = st.container()
            with action_col:
                action_left, action_right = st.columns(2)
                with action_left:
                    if st.button("Accept", key=f"trade_accept_{offer['id']}"):
                        offer["status"] = "Accepted"
                        trade_state["offers"].remove(offer)
                        trade_state["history"].insert(0, offer)
                        st.session_state[trade_state_key] = trade_state

                        transactions_key = f"transactions_{league_id}"
                        if transactions_key not in st.session_state:
                            st.session_state[transactions_key] = generate_transactions(league)
                        badge = "".join(word[0] for word in offer["from"].split()[:2]).upper()
                        st.session_state[transactions_key].insert(
                            0,
                            {
                                "team": offer["from"],
                                "team_badge": badge,
                                "type": "Trade",
                                "detail": f"{offer['from']} traded with {offer['to']}",
                                "time_label": "Just now",
                                "faab": None,
                                "priority": None,
                            },
                        )
                        st.success("Trade accepted.")
                        _rerun()
                with action_right:
                    if st.button("Reject", key=f"trade_reject_{offer['id']}"):
                        offer["status"] = "Rejected"
                        trade_state["offers"].remove(offer)
                        trade_state["history"].insert(0, offer)
                        st.session_state[trade_state_key] = trade_state
                        st.info("Trade rejected.")
                        _rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        st.markdown('<div class="trade-card"><div class="trade-title">Trade History</div>', unsafe_allow_html=True)
        if not history:
            st.caption("No trade history yet.")
        for offer in history:
            st.markdown(
                f"""
                <div class="trade-row">
                    <div><strong>{offer['from']}</strong> ↔ <strong>{offer['to']}</strong></div>
                    <div class="trade-status">{offer['status']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    analysis_options = offers + history
    if analysis_options:
        analysis_labels = [f"#{offer['id']} {offer['from']} ↔ {offer['to']}" for offer in analysis_options]
        analysis_choice = st.selectbox("Analyze trade", analysis_labels)
        selected_offer = analysis_options[analysis_labels.index(analysis_choice)]
        random.seed(str(selected_offer["id"]))
        team_a_delta = round(random.uniform(-12, 12), 1)
        team_b_delta = round(-team_a_delta, 1)
        balance_data = pd.DataFrame(
            {
                "Position": ["QB", "RB", "WR", "TE"],
                selected_offer["from"]: [random.randint(1, 3) for _ in range(4)],
                selected_offer["to"]: [random.randint(1, 3) for _ in range(4)],
            }
        )

        st.markdown('<div class="trade-card"><div class="trade-title">Trade Analyzer</div>', unsafe_allow_html=True)
        st.markdown(
            f"Projected Impact: **{selected_offer['from']} {team_a_delta:+} pts** · "
            f"**{selected_offer['to']} {team_b_delta:+} pts**"
        )
        st.bar_chart(balance_data.set_index("Position"), height=180)
        st.markdown("</div>", unsafe_allow_html=True)
elif selected_tab == "Waivers":
    st.subheader("Waivers")
    waivers_key = f"waivers_{league_id}"
    if waivers_key not in st.session_state:
        st.session_state[waivers_key] = generate_waivers(league)
    waivers = st.session_state[waivers_key]

    left_col, right_col = st.columns(2)
    with left_col:
        mode = st.radio("View", ["FAAB Budgets", "Priority Order"], horizontal=True)
        if mode == "FAAB Budgets":
            header = (
                '<div class="waiver-row waiver-header"><div>Team</div><div>FAAB</div><div>Priority</div></div>'
            )
            rows = []
            for entry in sorted(waivers["budgets"], key=lambda item: item["faab"], reverse=True):
                rows.append(
                    f"""
                    <div class="waiver-row">
                        <div>{entry['team']}</div>
                        <div>${entry['faab']}</div>
                        <div>{entry['priority']}</div>
                    </div>
                    """
                )
            st.markdown(
                f'<div class="waiver-card"><div class="waiver-title">FAAB Budgets</div>{header}{"".join(rows)}</div>',
                unsafe_allow_html=True,
            )
        else:
            header = '<div class="waiver-row waiver-header"><div>Team</div><div>Priority</div><div></div></div>'
            rows = []
            for entry in waivers["priority"]:
                rows.append(
                    f"""
                    <div class="waiver-row">
                        <div>{entry['team']}</div>
                        <div>{entry['priority']}</div>
                        <div></div>
                    </div>
                    """
                )
            st.markdown(
                f'<div class="waiver-card"><div class="waiver-title">Priority Order</div>{header}{"".join(rows)}</div>',
                unsafe_allow_html=True,
            )

    with right_col:
        players_seed_key = f"waiver_players_seed_{league_id}"
        if players_seed_key not in st.session_state:
            st.session_state[players_seed_key] = str(time.time_ns())
        waiver_players = generate_players_data(st.session_state[players_seed_key], count=140)["players"]
        free_agents = [player for player in waiver_players if player["availability"] == "FA"]
        owned_players = [player for player in waiver_players if player["availability"] == "Owned"]

        with st.form("waiver_add_drop"):
            st.markdown('<div class="waiver-card"><div class="waiver-title">Add / Drop</div>', unsafe_allow_html=True)
            team_choice = st.selectbox(
                "Team", [team["name"] for team in league["teams"]], key="waiver_team_choice"
            )
            add_player = st.selectbox(
                "Add", [player["name"] for player in free_agents][:30], key="waiver_add_player"
            )
            drop_player = st.selectbox(
                "Drop", [player["name"] for player in owned_players][:30], key="waiver_drop_player"
            )
            faab_bid = st.number_input("FAAB Bid", min_value=0, max_value=100, value=5, key="waiver_faab")
            submit_claim = st.form_submit_button("Submit Claim")
            st.markdown("</div>", unsafe_allow_html=True)

        if submit_claim:
            next_order = max([claim["order"] for claim in waivers["claims"]] + [0]) + 1
            waivers["claims"].append(
                {
                    "order": next_order,
                    "team": st.session_state["waiver_team_choice"],
                    "add": st.session_state["waiver_add_player"],
                    "drop": st.session_state["waiver_drop_player"],
                    "status": "Pending",
                }
            )
            st.session_state[waivers_key] = waivers
            st.success("Claim submitted.")

        preview_team = st.session_state.get("waiver_team_choice")
        if preview_team:
            preview_rows = []
            for entry in waivers["priority"]:
                marker = "→" if entry["team"] == preview_team else ""
                preview_rows.append(
                    f"<div class='waiver-row'><div>{entry['team']}</div><div>{entry['priority']}</div><div>{marker}</div></div>"
                )
            preview_header = (
                '<div class="waiver-row waiver-header"><div>Team</div><div>Priority</div><div></div></div>'
            )
            st.markdown(
                f'<div class="waiver-card"><div class="waiver-title">Priority Preview</div>{preview_header}{"".join(preview_rows)}</div>',
                unsafe_allow_html=True,
            )

        header = (
            '<div class="claim-row waiver-header"><div>#</div><div>Add</div><div>Drop</div><div>Status</div></div>'
        )
        rows = []
        for claim in waivers["claims"]:
            rows.append(
                f"""
                <div class="claim-row">
                    <div>{claim['order']}</div>
                    <div>{claim['team']} adds {claim['add']}</div>
                    <div>{claim['drop']}</div>
                    <div>{claim['status']}</div>
                </div>
                """
            )
        st.markdown(
            f'<div class="waiver-card"><div class="waiver-title">Pending Claims</div>{header}{"".join(rows)}</div>',
            unsafe_allow_html=True,
        )
elif selected_tab == "Schedule":
    st.subheader("Schedule")
    schedule_seed_key = f"schedule_seed_{league_id}"
    if schedule_seed_key not in st.session_state:
        st.session_state[schedule_seed_key] = str(time.time_ns())
    schedule_seed = st.session_state[schedule_seed_key]
    schedule_state_key = f"schedule_state_{league_id}"
    if schedule_state_key not in st.session_state:
        st.session_state[schedule_state_key] = generate_schedule(league, seed=schedule_seed, weeks=15)
    schedule_data = st.session_state[schedule_state_key]["weeks"]
    view_mode = st.radio("View", ["Week view", "Grid view"], horizontal=True)
    week_choice = st.selectbox("Week", list(range(1, 16)), index=selected_week - 1)
    matchups = schedule_data.get(week_choice, [])

    if view_mode == "Grid view":
        teams = [team["name"] for team in league["teams"]]
        weeks = list(range(1, 16))
        grid = {team: {} for team in teams}
        for week, week_matchups in schedule_data.items():
            for matchup in week_matchups:
                grid[matchup["home"]][week] = f"vs {matchup['away']}"
                grid[matchup["away"]][week] = f"at {matchup['home']}"

        header_cells = "".join(f"<th>W{week}</th>" for week in weeks)
        body_rows = []
        for team in teams:
            row_cells = []
            for week in weeks:
                row_cells.append(f"<td>{grid.get(team, {}).get(week, '-')}</td>")
            body_rows.append(f"<tr><td><strong>{team}</strong></td>{''.join(row_cells)}</tr>")

        st.markdown(
            f"""
            <div class="schedule-grid">
                <table>
                    <thead>
                        <tr><th>Team</th>{header_cells}</tr>
                    </thead>
                    <tbody>
                        {''.join(body_rows)}
                    </tbody>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        if not matchups:
            st.info("No matchups available.")
        else:
            cards = []
            for matchup in matchups:
                home_win = matchup["winner"] == "home"
                away_win = matchup["winner"] == "away"
                away_logo = team_logo_html(matchup["away"])
                home_logo = team_logo_html(matchup["home"])
                cards.append(
                    f"""
                    <div class="schedule-card">
                        <div class="schedule-row">
                            <div class="schedule-team {('schedule-winner' if away_win else '')}">{away_logo} {matchup['away']}</div>
                            <div class="schedule-score">{matchup['away_score']}</div>
                            <div class="schedule-proj">Proj {matchup['away_proj']}</div>
                        </div>
                        <div class="schedule-row">
                            <div class="schedule-team {('schedule-winner' if home_win else '')}">{home_logo} {matchup['home']}</div>
                            <div class="schedule-score">{matchup['home_score']}</div>
                            <div class="schedule-proj">Proj {matchup['home_proj']}</div>
                        </div>
                    </div>
                    """
                )
            st.markdown(f'<div class="schedule-shell">{"".join(cards)}</div>', unsafe_allow_html=True)
elif selected_tab == "Settings":
    st.subheader("Settings")
    status_options = ["off", "scheduled", "live", "complete"]
    selected_status = st.selectbox(
        "Draft status",
        status_options,
        index=status_options.index(draft_status),
    )
    if selected_status != draft_status:
        st.session_state[draft_status_key] = selected_status
        _rerun()

    if league.get("commissioner"):
        st.subheader("Commissioner Tools")

        with st.form("commissioner_reset_week"):
            reset_week = st.selectbox("Reset week scores", list(range(1, 16)))
            confirm_reset = st.checkbox("Confirm reset")
            reset_submit = st.form_submit_button("Reset week")
        if reset_submit and confirm_reset:
            schedule_state_key = f"schedule_state_{league_id}"
            if schedule_state_key not in st.session_state:
                st.session_state[schedule_state_key] = generate_schedule(league, seed=str(time.time_ns()), weeks=15)
            week_matchups = st.session_state[schedule_state_key]["weeks"].get(reset_week, [])
            for matchup in week_matchups:
                matchup["home_score"] = 0.0
                matchup["away_score"] = 0.0
                matchup["winner"] = "home"
            _toast(f"Week {reset_week} scores reset.")

        with st.form("commissioner_seeds"):
            teams = [team["name"] for team in league["teams"]]
            seeds = st.multiselect(
                "Set playoff seeds (top 4)",
                teams,
                default=st.session_state.get(playoff_seeds_key, teams[:4]),
                max_selections=4,
            )
            seed_submit = st.form_submit_button("Save seeds")
        if seed_submit:
            st.session_state[playoff_seeds_key] = seeds
            _toast("Playoff seeds updated.")

        with st.form("commissioner_swap_matchup"):
            swap_week = st.selectbox("Swap opponents for week", list(range(1, 16)), key="swap_week")
            team_names = [team["name"] for team in league["teams"]]
            team_a = st.selectbox("Team A", team_names, key="swap_team_a")
            team_b = st.selectbox("Team B", team_names, key="swap_team_b")
            confirm_swap = st.checkbox("Confirm swap")
            swap_submit = st.form_submit_button("Swap opponents")
        if swap_submit and confirm_swap:
            if team_a == team_b:
                st.error("Select two different teams.")
            else:
                schedule_state_key = f"schedule_state_{league_id}"
                if schedule_state_key not in st.session_state:
                    st.session_state[schedule_state_key] = generate_schedule(
                        league, seed=str(time.time_ns()), weeks=15
                    )
                matchups = st.session_state[schedule_state_key]["weeks"].get(swap_week, [])
                idx_a = idx_b = None
                side_a = side_b = None
                for idx, matchup in enumerate(matchups):
                    if matchup["home"] == team_a:
                        idx_a, side_a = idx, "home"
                    elif matchup["away"] == team_a:
                        idx_a, side_a = idx, "away"
                    if matchup["home"] == team_b:
                        idx_b, side_b = idx, "home"
                    elif matchup["away"] == team_b:
                        idx_b, side_b = idx, "away"

                if idx_a is None or idx_b is None or idx_a == idx_b:
                    st.error("Could not locate both teams in distinct matchups.")
                else:
                    matchup_a = matchups[idx_a]
                    matchup_b = matchups[idx_b]
                    opp_a = matchup_a["away"] if side_a == "home" else matchup_a["home"]
                    opp_b = matchup_b["away"] if side_b == "home" else matchup_b["home"]
                    if side_a == "home":
                        matchup_a["away"] = opp_b
                    else:
                        matchup_a["home"] = opp_b
                    if side_b == "home":
                        matchup_b["away"] = opp_a
                    else:
                        matchup_b["home"] = opp_a
                    matchup_a["home_score"] = 0.0
                    matchup_a["away_score"] = 0.0
                    matchup_b["home_score"] = 0.0
                    matchup_b["away_score"] = 0.0
                    matchup_a["winner"] = "home"
                    matchup_b["winner"] = "home"
                    _toast(f"Week {swap_week} opponents swapped.")

st.markdown("</div>", unsafe_allow_html=True)
