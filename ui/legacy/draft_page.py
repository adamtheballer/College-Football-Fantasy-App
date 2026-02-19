import html
import os
import sys
import textwrap
import time

import streamlit as st
import streamlit.components.v1 as components

from ui.lib import api_client
from ui.lib.theme import apply_theme

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

PLACEHOLDER_LEAGUES = [
    {"id": 1, "name": "CFB Draft League"},
]

PLACEHOLDER_TEAMS = [
    {"id": 1, "name": "Saturday Savages"},
    {"id": 2, "name": "Gridiron Ghosts"},
    {"id": 3, "name": "Fourth And Chaos"},
    {"id": 4, "name": "Victory Lane"},
    {"id": 5, "name": "Tailgate Titans"},
    {"id": 6, "name": "Hail Marys"},
    {"id": 7, "name": "Dynasty Dogs"},
    {"id": 8, "name": "Redzone Renegades"},
    {"id": 9, "name": "Blitz Brigade"},
    {"id": 10, "name": "Prime Time Pioneers"},
]

PLACEHOLDER_PLAYERS = [
    {"name": "Shedeur Sanders", "school": "Colorado", "position": "QB"},
    {"name": "Quinn Ewers", "school": "Texas", "position": "QB"},
    {"name": "Carson Beck", "school": "Georgia", "position": "QB"},
    {"name": "Dillon Gabriel", "school": "Oregon", "position": "QB"},
    {"name": "Jalen Milroe", "school": "Alabama", "position": "QB"},
    {"name": "Cam Ward", "school": "Miami", "position": "QB"},
    {"name": "Drew Allar", "school": "Penn State", "position": "QB"},
    {"name": "Ollie Gordon II", "school": "Oklahoma State", "position": "RB"},
    {"name": "Ashton Jeanty", "school": "Boise State", "position": "RB"},
    {"name": "Quinshon Judkins", "school": "Ohio State", "position": "RB"},
    {"name": "TreVeyon Henderson", "school": "Ohio State", "position": "RB"},
    {"name": "Nicholas Singleton", "school": "Penn State", "position": "RB"},
    {"name": "Donovan Edwards", "school": "Michigan", "position": "RB"},
    {"name": "Omarion Hampton", "school": "North Carolina", "position": "RB"},
    {"name": "Damien Martinez", "school": "Miami", "position": "RB"},
    {"name": "Tetairoa McMillan", "school": "Arizona", "position": "WR"},
    {"name": "Luther Burden III", "school": "Missouri", "position": "WR"},
    {"name": "Emeka Egbuka", "school": "Ohio State", "position": "WR"},
    {"name": "Evan Stewart", "school": "Oregon", "position": "WR"},
    {"name": "Travis Hunter", "school": "Colorado", "position": "WR"},
    {"name": "Isaiah Bond", "school": "Texas", "position": "WR"},
    {"name": "Tre Harris", "school": "Ole Miss", "position": "WR"},
    {"name": "Jeremiah Smith", "school": "Ohio State", "position": "WR"},
    {"name": "Elic Ayomanor", "school": "Stanford", "position": "WR"},
    {"name": "Colston Loveland", "school": "Michigan", "position": "TE"},
    {"name": "Oscar Delp", "school": "Georgia", "position": "TE"},
    {"name": "Mason Taylor", "school": "LSU", "position": "TE"},
    {"name": "Harold Fannin Jr", "school": "Bowling Green", "position": "TE"},
    {"name": "Camden Brown", "school": "Penn State", "position": "WR"},
    {"name": "Nyck Harbor", "school": "South Carolina", "position": "WR"},
    {"name": "Xavier Restrepo", "school": "Miami", "position": "WR"},
    {"name": "Deion Burks", "school": "Oklahoma", "position": "WR"},
    {"name": "Jabbar Muhammad", "school": "Oregon", "position": "WR"},
]

DRAFT_CSS = '''
<style>
@import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600&family=Space+Grotesk:wght@400;500;600&display=swap');

:root {
    --bg-main: #000000;
    --bg-surface: #1a1a1a;
    --bg-surface-2: #242424;
    --text-primary: #f5f5f5;
    --text-muted: #9ca3af;
    --border-subtle: #333333;
    --accent-green: #4caf50;
    --accent-blue: #5bb0ff;
    --danger: #ff4444;
}

html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #000000 0%, #1a1a1a 100%);
    color: var(--text-primary);
    font-family: "Space Grotesk", "Chakra Petch", sans-serif;
}

section.main {
    padding: 0;
}

div.block-container {
    max-width: 100%;
    padding: 0 24px 120px;
}

@media (max-width: 768px) {
    div.block-container {
        padding: 0 12px 110px;
    }
}

header, footer {
    visibility: hidden;
}

div[data-testid="stVerticalBlock"]:has(#draft-top) {
    position: sticky;
    top: 0;
    z-index: 50;
    background: rgba(0, 0, 0, 0.95);
    border-bottom: 1px solid var(--border-subtle);
    padding: 12px 0;
}

div[data-testid="stVerticalBlock"]:has(#draft-sub) {
    position: sticky;
    top: 68px;
    z-index: 45;
    background: rgba(10, 10, 10, 0.95);
    border-bottom: 1px solid var(--border-subtle);
    padding: 8px 0;
}

div[data-testid="stVerticalBlock"]:has(#draft-filters) {
    position: sticky;
    top: 108px;
    z-index: 40;
    background: rgba(10, 10, 10, 0.96);
    border-bottom: 1px solid var(--border-subtle);
    padding: 10px 0;
}

.draft-team {
    text-align: center;
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
}

.draft-countdown-label {
    text-align: center;
    font-size: 13px;
    color: var(--text-muted);
}

.draft-countdown {
    text-align: center;
    font-family: "Chakra Petch", sans-serif;
    font-size: 28px;
    font-weight: 600;
    margin-top: 2px;
}

.draft-countdown.urgent {
    color: var(--danger);
    animation: pulse 1s infinite;
}

@keyframes pulse {
    0%,
    100% {
        opacity: 1;
    }
    50% {
        opacity: 0.7;
    }
}

.draft-subline {
    text-align: center;
    font-size: 14px;
    color: var(--text-primary);
    letter-spacing: 0.4px;
}

.round-row {
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 12px;
    align-items: center;
    margin: 12px 0 16px;
}

.round-label {
    font-size: 13px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
}

.pick-strip {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding-bottom: 4px;
}

.draft-pick {
    background: var(--bg-surface);
    border-radius: 10px;
    border: 1px solid var(--border-subtle);
    padding: 10px;
    min-width: 140px;
}

.draft-pick.active {
    border-color: var(--accent-green);
    box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
}

.draft-pick.user-pick {
    background: rgba(76, 175, 80, 0.12);
    border-color: var(--accent-green);
}

.pick-label {
    font-size: 12px;
    color: var(--text-muted);
}

.pick-team {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.pick-auto {
    margin-top: 6px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--accent-green);
    border: 1px solid rgba(76, 175, 80, 0.4);
    border-radius: 999px;
    padding: 3px 6px;
    width: max-content;
}

div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    color: var(--text-primary);
}

div[data-baseweb="select"] > div:hover,
div[data-baseweb="input"] > div:hover {
    border-color: #555555;
}

div[data-testid="stVerticalBlock"]:has(#player-table) div[data-testid="stHorizontalBlock"] {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 8px 12px;
    margin-bottom: 8px;
    align-items: center;
}

div[data-testid="stVerticalBlock"]:has(#player-table) div[data-testid="stHorizontalBlock"]:first-of-type {
    background: transparent;
    border: none;
    padding: 0 6px 6px;
    margin-bottom: 8px;
}

div[data-testid="stVerticalBlock"]:has(#player-table) div[data-testid="stHorizontalBlock"]:not(:first-of-type) {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    cursor: pointer;
    position: relative;
}

div[data-testid="stVerticalBlock"]:has(#player-table) div[data-testid="stHorizontalBlock"]:not(:first-of-type):hover {
    transform: translateY(-4px) scale(1.01);
    background: rgba(255, 255, 255, 0.08) !important;
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(76, 175, 80, 0.3);
    border-radius: 12px;
    z-index: 10;
}

.player-name {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    color: var(--accent-blue);
    font-weight: 600;
}

.player-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 2px;
}

.player-school {
    font-size: 12px;
    color: var(--text-muted);
}

.pos-chip {
    border-radius: 999px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.4px;
}

.pos-qb {
    background: #bfe3ff;
    color: #1e293b;
}

.pos-rb {
    background: #ffd6a5;
    color: #3f1d0f;
}

.pos-wr {
    background: #d0f4de;
    color: #14532d;
}

.pos-te {
    background: #fff3b0;
    color: #4b5563;
}

.pos-k {
    background: #e1baff;
    color: #3b0764;
}

div[data-testid="stVerticalBlock"]:has(#player-table) div[data-testid="stHorizontalBlock"]:not(:first-of-type):hover .player-name {
    color: var(--accent-green) !important;
    font-weight: 700;
    text-shadow: 0 0 8px rgba(76, 175, 80, 0.5);
    transform: translateY(-1px);
}

.queue-btn {
    background: #333333;
    border: 1px solid #555555;
    color: #ffffff;
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    transition: all 0.2s ease;
}

.queue-btn:hover {
    background: #444444;
    border-color: #666666;
}

div[data-testid="stVerticalBlock"]:has(#player-table) button[kind="primary"],
div[data-testid="stVerticalBlock"]:has(#player-table) button[kind="secondary"] {
    border-radius: 999px !important;
    padding: 6px 14px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}

div[data-testid="stVerticalBlock"]:has(#player-table) button[kind="primary"] {
    background: var(--accent-green) !important;
    border-color: var(--accent-green) !important;
    color: #0c120d !important;
}

div[data-testid="stVerticalBlock"]:has(#player-table) button[kind="primary"]:hover {
    background: #5ebf64 !important;
    border-color: #5ebf64 !important;
}

div[data-testid="stVerticalBlock"]:has(#player-table) button[kind="secondary"] {
    background: #1f1f1f !important;
    border: 1px solid #444444 !important;
    color: #ffffff !important;
}

div[data-testid="stVerticalBlock"]:has(#player-table) button[kind="secondary"]:hover {
    background: #2a2a2a !important;
    border-color: #666666 !important;
}

.bottom-nav {
    background: linear-gradient(180deg, #000000 0%, #1a1a1a 100%);
    border-top: 1px solid #333333;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 50;
    padding: 12px 16px;
    padding-bottom: calc(12px + env(safe-area-inset-bottom));
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
}

.nav-item {
    display: grid;
    justify-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

.nav-item.active {
    color: var(--accent-green);
}

.nav-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 999px;
    background: #2b6cb0;
    color: #ffffff;
    font-size: 10px;
    font-weight: 700;
}

.draft-header-button button {
    background: transparent !important;
    border: 1px solid #333333 !important;
    color: #ffffff !important;
    border-radius: 999px !important;
    padding: 6px 12px !important;
    font-size: 12px !important;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

div[data-testid="stVerticalBlock"]:has(#draft-settings) {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 12px;
    margin: 12px 0;
}
</style>
'''


def _get_team_on_clock(order: list[dict], pick_index: int, snake: bool) -> tuple[dict, int, int]:
    team_count = len(order)
    round_index = pick_index // team_count
    pick_in_round = pick_index % team_count
    if snake and round_index % 2 == 1:
        team_index = team_count - 1 - pick_in_round
    else:
        team_index = pick_in_round
    return order[team_index], round_index + 1, pick_in_round + 1


def _escape(text: str) -> str:
    return html.escape(text)


def _position_class(position: str) -> str:
    return {
        "QB": "pos-qb",
        "RB": "pos-rb",
        "WR": "pos-wr",
        "TE": "pos-te",
        "K": "pos-k",
    }.get(position, "pos-qb")


def _render_html(html_text: str) -> None:
    cleaned = textwrap.dedent(html_text).strip()
    cleaned = "\n".join(line.lstrip() for line in cleaned.splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)


def _ordinal(value: int) -> str:
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _format_time(seconds: int) -> str:
    minutes = seconds // 60
    remainder = seconds % 60
    return f"{minutes:02d}:{remainder:02d}"


def _load_leagues() -> list[dict]:
    try:
        leagues = api_client.get_leagues()["data"]
    except Exception:
        leagues = []
    return leagues or PLACEHOLDER_LEAGUES


def _load_teams(league_id: int) -> list[dict]:
    try:
        teams = api_client.get_teams(league_id)["data"]
    except Exception:
        teams = []
    return teams or PLACEHOLDER_TEAMS


def _build_placeholder_players(start_id: int) -> list[dict]:
    players = []
    next_id = start_id
    for entry in PLACEHOLDER_PLAYERS:
        players.append(
            {
                "id": next_id,
                "name": entry["name"],
                "position": entry["position"],
                "school": entry["school"],
            }
        )
        next_id += 1
    return players


def _load_players() -> list[dict]:
    try:
        players = api_client.get_players({"limit": 500})["data"]
    except Exception:
        players = []
    players = list(players or [])
    existing_names = {player["name"].lower() for player in players if "name" in player}
    next_id = max((player.get("id", 0) for player in players), default=0) + 1
    for entry in _build_placeholder_players(next_id):
        if entry["name"].lower() in existing_names:
            continue
        players.append(entry)
    return players


def _render_timer(label_text: str, remaining_seconds: int, urgent: bool, auto_reload: bool) -> None:
    timer_class = "urgent" if urgent else ""
    auto_reload_flag = "true" if auto_reload else "false"
    timer_html = f"""
    <!doctype html>
    <html>
        <head>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600&display=swap');
                body {{
                    margin: 0;
                    background: transparent;
                    color: #f5f5f5;
                    font-family: "Chakra Petch", sans-serif;
                    text-align: center;
                }}
                .label {{
                    font-size: 13px;
                    color: #9ca3af;
                }}
                .timer {{
                    font-size: 28px;
                    font-weight: 600;
                    margin-top: 2px;
                }}
                .urgent {{
                    color: #ff4444;
                    animation: pulse 1s infinite;
                }}
                @keyframes pulse {{
                    0%, 100% {{ opacity: 1; }}
                    50% {{ opacity: 0.7; }}
                }}
            </style>
        </head>
        <body>
            <div class="label">{label_text}</div>
            <div id="timer" class="timer {timer_class}">{_format_time(remaining_seconds)}</div>
            <script>
                const autoReload = {auto_reload_flag};
                const start = Date.now();
                const duration = {remaining_seconds} * 1000;
                let didReload = false;
                const formatTime = (seconds) => {{
                    const mins = Math.floor(seconds / 60);
                    const secs = seconds % 60;
                    return `${{String(mins).padStart(2, "0")}}:${{String(secs).padStart(2, "0")}}`;
                }};
                const tick = () => {{
                    const elapsed = Date.now() - start;
                    const remaining = Math.max(0, duration - elapsed);
                    const seconds = Math.floor(remaining / 1000);
                    document.getElementById("timer").textContent = formatTime(seconds);
                    if (autoReload && seconds <= 0 && !didReload) {{
                        didReload = true;
                        window.parent.location.reload();
                    }}
                }};
                tick();
                if (autoReload) {{
                    setInterval(tick, 1000);
                }}
            </script>
        </body>
    </html>
    """
    components.html(timer_html, height=70, scrolling=False)


st.set_page_config(page_title="Draft", layout="wide")
apply_theme()
_render_html(DRAFT_CSS)

if "draft_auto_pick" not in st.session_state:
    st.session_state["draft_auto_pick"] = False
if "draft_hide_drafted" not in st.session_state:
    st.session_state["draft_hide_drafted"] = True
if "draft_queue" not in st.session_state:
    st.session_state["draft_queue"] = []
if "draft_start_seconds" not in st.session_state:
    st.session_state["draft_start_seconds"] = 46
if "draft_start_seconds_prev" not in st.session_state:
    st.session_state["draft_start_seconds_prev"] = st.session_state["draft_start_seconds"]
if "draft_countdown_start" not in st.session_state:
    st.session_state["draft_countdown_start"] = time.time()
if "draft_started" not in st.session_state:
    st.session_state["draft_started"] = False
if "draft_position_filter" not in st.session_state:
    st.session_state["draft_position_filter"] = "All Pos"
if "draft_sort" not in st.session_state:
    st.session_state["draft_sort"] = "Proj Pts"
if "draft_search" not in st.session_state:
    st.session_state["draft_search"] = ""
if "draft_show_settings" not in st.session_state:
    st.session_state["draft_show_settings"] = False

leagues = _load_leagues()
league_options = {f"{league['name']} (#{league['id']})": league for league in leagues}
if "draft_league_label" not in st.session_state and league_options:
    st.session_state["draft_league_label"] = list(league_options.keys())[0]

selected_label = st.session_state.get("draft_league_label")
selected_league = league_options.get(selected_label)
if not selected_league:
    st.info("Create a league to start a draft.")
    st.stop()

teams = _load_teams(selected_league["id"])
if not teams:
    st.info("Add teams to start a draft.")
    st.stop()

players = _load_players()
players_by_id = {player["id"]: player for player in players}
team_ids = {team["id"] for team in teams}

if "draft_user_team" not in st.session_state or st.session_state["draft_user_team"] not in team_ids:
    st.session_state["draft_user_team"] = teams[0]["id"]

if st.session_state["draft_start_seconds"] != st.session_state["draft_start_seconds_prev"]:
    st.session_state["draft_start_seconds_prev"] = st.session_state["draft_start_seconds"]
    st.session_state["draft_countdown_start"] = time.time()
    st.session_state["draft_started"] = False

elapsed = int(time.time() - st.session_state["draft_countdown_start"])
remaining_seconds = max(0, st.session_state["draft_start_seconds"] - elapsed)
if remaining_seconds == 0:
    st.session_state["draft_started"] = True

draft_state = st.session_state.get("draft_state")
if draft_state and draft_state.get("league_id") != selected_league["id"]:
    st.warning("Draft state is for another league. Reset to start a new draft.")
    draft_state = None
    st.session_state["draft_state"] = None

if st.session_state["draft_started"] and not draft_state:
    draft_state = {
        "league_id": selected_league["id"],
        "rounds": 1,
        "snake": False,
        "order": [{"id": team["id"], "name": team["name"]} for team in teams],
        "picks": [],
    }
    st.session_state["draft_state"] = draft_state

if draft_state:
    drafted_player_ids = {pick["player_id"] for pick in draft_state["picks"]}
else:
    drafted_player_ids = set()

total_picks = 0
pick_index = 0
team_on_clock = None
round_number = 0
pick_in_round = 0

if draft_state:
    total_picks = draft_state["rounds"] * len(draft_state["order"])
    pick_index = len(draft_state["picks"])
    if pick_index < total_picks:
        team_on_clock, round_number, pick_in_round = _get_team_on_clock(
            draft_state["order"], pick_index, draft_state["snake"]
        )

queue_ids = {player_id for player_id in st.session_state["draft_queue"] if player_id in players_by_id}

player_metrics: dict[int, dict] = {}
ordered_players = sorted(players, key=lambda item: item["name"].lower())
for index, player in enumerate(ordered_players, start=1):
    proj_value = max(120.0, 360.0 - index * 2.4)
    adp_value = 1.0 + index * 0.6
    bye_week = (index % 14) + 1
    player_metrics[player["id"]] = {
        "rank": index,
        "proj": proj_value,
        "adp": adp_value,
        "bye": bye_week,
    }

with st.container():
    _render_html('<div id="draft-top"></div>')
    left, center, right = st.columns([1, 2, 1])
    with left:
        with st.container():
            st.markdown('<div class="draft-header-button">', unsafe_allow_html=True)
            st.button("Exit", key="draft_exit")
            st.markdown("</div>", unsafe_allow_html=True)
    with center:
        if st.session_state["draft_started"] and team_on_clock:
            _render_html(f'<div class="draft-team">{_escape(team_on_clock["name"])}</div>')
            label_text = "On the clock"
        else:
            label_text = "Draft starts in"
        urgent = remaining_seconds <= 10 and not st.session_state["draft_started"]
        auto_reload = not st.session_state["draft_started"] and remaining_seconds > 0
        _render_timer(label_text, remaining_seconds, urgent, auto_reload)
    with right:
        with st.container():
            st.markdown('<div class="draft-header-button">', unsafe_allow_html=True)
            if st.button("Settings", key="draft_settings"):
                st.session_state["draft_show_settings"] = not st.session_state["draft_show_settings"]
            st.markdown("</div>", unsafe_allow_html=True)

if st.session_state["draft_show_settings"]:
    with st.container():
        _render_html('<div id="draft-settings"></div>')
        st.markdown("**Draft settings**")
        st.selectbox("League", list(league_options.keys()), key="draft_league_label")
        st.selectbox(
            "Your team",
            [team["id"] for team in teams],
            format_func=lambda team_id: next(team["name"] for team in teams if team["id"] == team_id),
            key="draft_user_team",
        )
        st.number_input(
            "Draft countdown (seconds)",
            min_value=0,
            max_value=180,
            value=st.session_state["draft_start_seconds"],
            key="draft_start_seconds",
        )
        st.checkbox("Hide drafted players", key="draft_hide_drafted")
        if st.button("Reset countdown"):
            st.session_state["draft_countdown_start"] = time.time()
            st.session_state["draft_started"] = False
            st.success("Countdown reset.")
        if st.button("Reset draft"):
            st.session_state["draft_state"] = None
            st.session_state["draft_queue"] = []
            st.session_state["draft_started"] = False
            st.session_state["draft_countdown_start"] = time.time()
            st.success("Draft reset.")

pick_display = "You pick --"
user_team_id = st.session_state["draft_user_team"]
if draft_state:
    for index, team in enumerate(draft_state["order"], start=1):
        if team["id"] == user_team_id:
            pick_display = f"You pick {_ordinal(index)}"
            break

with st.container():
    _render_html('<div id="draft-sub"></div>')
    _render_html(f'<div class="draft-subline">{pick_display}</div>')

pick_order = draft_state["order"] if draft_state else [{"id": team["id"], "name": team["name"]} for team in teams]
cards = []
for index, team in enumerate(pick_order, start=1):
    team_name = _escape(team["name"])
    active_class = "active" if pick_index + 1 == index else ""
    user_class = "user-pick" if team["id"] == user_team_id else ""
    auto_badge = ""
    if st.session_state["draft_auto_pick"] and team["id"] == user_team_id:
        auto_badge = "<div class=\"pick-auto\">AUTO</div>"
    cards.append(
        f"""
        <div class=\"draft-pick {active_class} {user_class}\">
            <div class=\"pick-label\">Pick {index}</div>
            <div class=\"pick-team\">{team_name}</div>
            {auto_badge}
        </div>
        """
    )

_render_html(
    f'''
    <div class="round-row">
        <div class="round-label">Round 1</div>
        <div class="pick-strip">{''.join(cards)}</div>
    </div>
    '''
)

with st.container():
    _render_html('<div id="draft-filters"></div>')
    position_col, sort_col, reset_col, search_col = st.columns([1.2, 1.2, 0.7, 1.9])
    with position_col:
        position_options = ["All Pos", "QB", "RB", "WR", "TE"]
        st.selectbox("Position", position_options, key="draft_position_filter", label_visibility="collapsed")
    with sort_col:
        sort_options = ["Proj Pts", "ADP", "Rank", "Name"]
        st.selectbox("Sort", sort_options, key="draft_sort", label_visibility="collapsed")
    with reset_col:
        if st.button("Reset", key="draft_reset"):
            st.session_state["draft_position_filter"] = "All Pos"
            st.session_state["draft_sort"] = "Proj Pts"
            st.session_state["draft_search"] = ""
    with search_col:
        st.text_input(
            "Search",
            key="draft_search",
            label_visibility="collapsed",
            placeholder="Search players",
        )

position_choice = st.session_state["draft_position_filter"]
position_filter = None if position_choice == "All Pos" else position_choice
normalized_query = st.session_state["draft_search"].strip().lower()

filtered_players: list[dict] = []
for player in players:
    if position_filter and player["position"] != position_filter:
        continue
    if normalized_query and normalized_query not in player["name"].lower() and normalized_query not in player["school"].lower():
        continue
    if st.session_state["draft_hide_drafted"] and player["id"] in drafted_player_ids:
        continue
    filtered_players.append(player)

sort_option = st.session_state["draft_sort"]
if sort_option == "Proj Pts":
    filtered_players.sort(key=lambda item: player_metrics[item["id"]]["proj"], reverse=True)
elif sort_option == "ADP":
    filtered_players.sort(key=lambda item: player_metrics[item["id"]]["adp"])
elif sort_option == "Rank":
    filtered_players.sort(key=lambda item: player_metrics[item["id"]]["rank"])
elif sort_option == "Name":
    filtered_players.sort(key=lambda item: item["name"].lower())

if not filtered_players:
    st.info("No players match the current filters.")
else:
    _render_html('<div id="player-table"></div>')
    header_cols = st.columns([0.6, 2.6, 0.7, 0.8, 0.9, 1.2])
    with header_cols[0]:
        st.markdown("RK")
    with header_cols[1]:
        st.markdown("PLAYER")
    with header_cols[2]:
        st.markdown("BYE")
    with header_cols[3]:
        st.markdown("ADP")
    with header_cols[4]:
        st.markdown("PROJ")
    with header_cols[5]:
        st.markdown("")

    for player in filtered_players[:60]:
        metrics = player_metrics[player["id"]]
        rank_value = metrics["rank"]
        bye_week = metrics["bye"]
        adp_value = metrics["adp"]
        projection_value = metrics["proj"]
        row_cols = st.columns([0.6, 2.6, 0.7, 0.8, 0.9, 1.2])
        with row_cols[0]:
            st.markdown(str(rank_value))
        with row_cols[1]:
            st.markdown(f"<span class=\"player-name\">{_escape(player['name'])}</span>", unsafe_allow_html=True)
            pos_class = _position_class(player["position"])
            st.markdown(
                f"""
                <div class="player-meta">
                    <span class="pos-chip {pos_class}">{_escape(player['position'])}</span>
                    <span class="player-school">{_escape(player['school'])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with row_cols[2]:
            st.markdown(str(bye_week))
        with row_cols[3]:
            st.markdown(f"{adp_value:.1f}")
        with row_cols[4]:
            st.markdown(f"{projection_value:.1f}")
        with row_cols[5]:
            is_queued = player["id"] in queue_ids
            if st.session_state["draft_started"]:
                label = "DRAFT"
                button_type = "primary"
            else:
                label = "QUEUED" if is_queued else "QUEUE"
                button_type = "secondary"
            if st.button(label, key=f"queue_{player['id']}", type=button_type):
                if st.session_state["draft_started"]:
                    if not draft_state or not team_on_clock:
                        st.warning("Draft order not ready yet.")
                    else:
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
                        if player["id"] in st.session_state["draft_queue"]:
                            st.session_state["draft_queue"].remove(player["id"])
                        st.success(f"{team_on_clock['name']} drafted {player['name']}.")
                else:
                    if is_queued:
                        st.session_state["draft_queue"].remove(player["id"])
                    else:
                        st.session_state["draft_queue"].append(player["id"])

queue_count = len(queue_ids)
queue_badge = f"<span class=\"nav-badge\">{queue_count}</span>" if queue_count else ""

_render_html(
    f'''
    <div class="bottom-nav">
        <div class="nav-item active">Players</div>
        <div class="nav-item">Queue {queue_badge}</div>
        <div class="nav-item">Board</div>
        <div class="nav-item">Rosters</div>
    </div>
    '''
)
