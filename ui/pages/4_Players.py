import os
import random
import sys
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib import api_client
from ui.lib.components.sidebar import render_sidebar_nav
from ui.lib.components.top_nav import render_top_nav
from urllib.parse import urlencode

from ui.lib.mock.league import generate_league_data
from ui.lib.mock.players import generate_players_data
from ui.lib.theme import apply_theme

apply_theme()
render_sidebar_nav("players")
render_top_nav("players")
st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] .main .block-container {
        max-width: 1280px;
        padding-left: 2.6rem;
        padding-right: 2.6rem;
    }

    .players-tabs {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.4rem;
        margin-bottom: 0.6rem;
    }

    .players-tab {
        text-align: center;
        padding: 0.45rem 0;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #9fb0c7;
        border-bottom: 2px solid transparent;
        position: relative;
    }

    .players-tab.active {
        color: #cfe1ff;
        border-bottom: 2px solid #2ed158;
    }

    .players-controls {
        display: grid;
        grid-template-columns: 36px 36px 36px 1fr;
        gap: 0.6rem;
        align-items: center;
        margin-bottom: 0.6rem;
    }

    .icon-wrap button {
        width: 36px;
        height: 36px;
        border-radius: 50% !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: #cfe1ff !important;
        font-size: 0.85rem;
        background: rgba(255, 255, 255, 0.04) !important;
        padding: 0 !important;
    }

    .icon-wrap.active button {
        box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.6);
    }

    .chip-row {
        display: flex;
        gap: 0.4rem;
        overflow-x: auto;
        padding-bottom: 0.2rem;
        margin-bottom: 0.8rem;
    }

    .chip-row::-webkit-scrollbar {
        display: none;
    }

    .chip {
        padding: 0.35rem 0.8rem;
        border-radius: 999px;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        border: 1px solid rgba(255, 255, 255, 0.16);
        color: #9fb0c7;
        background: transparent;
        white-space: nowrap;
        text-decoration: none;
    }

    .chip.active {
        background: rgba(74, 163, 255, 0.2);
        border-color: rgba(74, 163, 255, 0.5);
        color: #e0ecff;
    }

    .watch-divider {
        height: 1px;
        background: rgba(255, 255, 255, 0.06);
        margin: 0.4rem 0 0.8rem;
    }

    .watch-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 1rem;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        background: rgba(255, 255, 255, 0.04);
    }

    .watch-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.12rem;
        color: #cfe1ff;
        font-weight: 700;
    }

    .watch-actions {
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }

    .watch-icon {
        width: 30px;
        height: 30px;
        border-radius: 50%;
        border: 1px solid rgba(255, 255, 255, 0.2);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        text-decoration: none;
        color: #cfe1ff;
        font-size: 0.7rem;
        background: rgba(255, 255, 255, 0.06);
    }

    .watch-dropdown {
        position: relative;
    }

    .watch-dropdown summary {
        list-style: none;
        cursor: pointer;
        padding: 0.35rem 0.8rem;
        border-radius: 999px;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(255, 255, 255, 0.04);
        font-size: 0.7rem;
        color: #cfe1ff;
    }

    .watch-dropdown[open] summary {
        border-color: rgba(74, 163, 255, 0.5);
    }

    .watch-dropdown summary::-webkit-details-marker {
        display: none;
    }

    .watch-dropdown-menu {
        position: absolute;
        right: 0;
        top: 110%;
        background: #0f151c;
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 10px;
        padding: 0.3rem 0;
        min-width: 160px;
        z-index: 10;
        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
    }

    .watch-dropdown-menu a {
        display: block;
        padding: 0.4rem 0.7rem;
        text-decoration: none;
        color: #cfe1ff;
        font-size: 0.7rem;
    }

    .watch-dropdown-menu a:hover {
        background: rgba(255, 255, 255, 0.08);
    }

    .watch-list {
        position: relative;
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        overflow: hidden;
    }

    .watch-row {
        display: grid;
        grid-template-columns: 1fr 70px 70px;
        gap: 0;
        padding: 0.9rem 1rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
        font-size: 0.8rem;
        align-items: center;
        cursor: pointer;
    }

    .watch-row:last-child {
        border-bottom: none;
    }

    .watch-header-row {
        display: grid;
        grid-template-columns: 1fr 70px 70px;
        padding: 0.65rem 1rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        font-size: 0.62rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #7f8da3;
    }

    .player-left {
        display: grid;
        grid-template-columns: 28px 38px 1fr;
        gap: 0.7rem;
        align-items: center;
    }

    .add-btn {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: #2ed158;
        color: #0b0f14;
        font-weight: 800;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        text-decoration: none;
    }

    .add-btn.disabled {
        background: rgba(255, 255, 255, 0.1);
        color: #7f8da3;
        pointer-events: none;
    }

    .player-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.1);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.7rem;
        position: relative;
    }

    .player-ir {
        position: absolute;
        bottom: -6px;
        left: -4px;
        background: #ff5b5b;
        color: #ffffff;
        border-radius: 6px;
        font-size: 0.55rem;
        padding: 1px 4px;
        text-transform: uppercase;
        font-weight: 700;
    }

    .player-name {
        font-weight: 700;
        color: #f3f6ff;
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.2rem;
        font-size: 0.82rem;
        line-height: 1.2;
    }

    .player-meta {
        color: #9fb0c7;
        font-size: 0.65rem;
        margin-left: 0.35rem;
        text-transform: uppercase;
        letter-spacing: 0.06rem;
    }

    .note-icon {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 2px;
        background: rgba(255, 255, 255, 0.35);
        margin-left: 0.4rem;
    }

    .player-sub {
        color: #8fa0b6;
        font-size: 0.7rem;
        line-height: 1.3;
    }

    .player-matchup {
        font-size: 0.7rem;
        line-height: 1.3;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #7f8da3;
    }

    .player-link {
        text-decoration: none;
        color: inherit;
        display: block;
    }

    .trend-up {
        color: #42d17c;
        font-weight: 700;
    }

    .trend-down {
        color: #ff6b6b;
        font-weight: 700;
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
        st.query_params.clear()
        for key, value in params.items():
            st.query_params[key] = value
    else:
        st.experimental_set_query_params(**params)


params = _get_query_params()


def _first_param(key: str) -> str | None:
    value = params.get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _toast(message: str) -> None:
    if hasattr(st, "toast"):
        st.toast(message)
    else:
        st.success(message)


pos_param = _first_param("pos")
view_param = _first_param("view")
add_param = _first_param("add")
watch_param = _first_param("watch")

st.header("Waiver Wire")
st.caption("Undrafted players available to add and drop.")

watchlist_only = st.session_state.get("watchlist_only", True)
control_cols = st.columns([1, 1, 1, 4])
with control_cols[0]:
    st.markdown('<div class="icon-wrap">', unsafe_allow_html=True)
    st.button("🔍", key="icon_search", disabled=True)
    st.markdown("</div>", unsafe_allow_html=True)
with control_cols[1]:
    st.markdown('<div class="icon-wrap">', unsafe_allow_html=True)
    st.button("🎚", key="icon_filter", disabled=True)
    st.markdown("</div>", unsafe_allow_html=True)
with control_cols[2]:
    wrap_class = "icon-wrap active" if watchlist_only else "icon-wrap"
    st.markdown(f'<div class="{wrap_class}">', unsafe_allow_html=True)
    if st.button("⚑", key="watchlist_toggle"):
        st.session_state["watchlist_only"] = not watchlist_only
        watchlist_only = st.session_state["watchlist_only"]
    st.markdown("</div>", unsafe_allow_html=True)
with control_cols[3]:
    search_query = st.text_input("", placeholder="Search", label_visibility="collapsed")

chip_options = ["All", "QB", "RB", "WR", "TE", "K"]
position_filter = pos_param if pos_param in chip_options else "All"
view_label_map = {
    "matchup": "Matchup Stats",
    "season": "Season Stats",
    "proj": "Projections",
    "last3": "Last 3",
}
view_choice = view_param if view_param in view_label_map else "matchup"
view_label = view_label_map.get(view_choice, "Matchup Stats")

chip_links = []
for option in chip_options:
    query = urlencode({"pos": option, "view": view_choice})
    active_class = "active" if option == position_filter else ""
    chip_links.append(f'<a class="chip {active_class}" href="?{query}">{option}</a>')
st.markdown(f'<div class="chip-row">{"".join(chip_links)}</div>', unsafe_allow_html=True)

league_id = st.session_state.get("selected_league_id", 1)
league_state_key = f"league_state_{league_id}"
if league_state_key not in st.session_state:
    st.session_state[league_state_key] = generate_league_data(league_id)["league"]
league = st.session_state[league_state_key]

players_seed_key = f"waiver_pool_{league_id}"
if players_seed_key not in st.session_state:
    st.session_state[players_seed_key] = str(datetime.now().timestamp())

@st.cache_data(show_spinner=False)
def _get_waiver_pool(seed: str) -> dict:
    return generate_players_data(seed, count=220)

players_pool = _get_waiver_pool(st.session_state[players_seed_key])["players"]
players_by_id = {player["id"]: player for player in players_pool}

rosters_key = f"rosters_{league_id}"
if rosters_key not in st.session_state:
    random.seed(st.session_state[players_seed_key])
    rosters = {team["id"]: [] for team in league["teams"]}
    drafted = random.sample(players_pool, k=min(len(players_pool), len(league["teams"]) * 12))
    for idx, player in enumerate(drafted):
        team_id = league["teams"][idx % len(league["teams"])]["id"]
        rosters[team_id].append(player["id"])
    st.session_state[rosters_key] = rosters

rosters = st.session_state[rosters_key]
drafted_ids = {player_id for roster in rosters.values() for player_id in roster}
waiver_players = [player for player in players_pool if player["id"] not in drafted_ids]

watchlist_key = f"watchlist_{league_id}"
if watchlist_key not in st.session_state:
    random.seed(st.session_state[players_seed_key])
    st.session_state[watchlist_key] = {
        player["id"] for player in random.sample(waiver_players, k=min(28, len(waiver_players)))
    }
watchlist_ids = st.session_state[watchlist_key]

if watch_param:
    try:
        watch_id = int(watch_param)
    except ValueError:
        watch_id = None
    if watch_id:
        if watch_id in watchlist_ids:
            watchlist_ids.remove(watch_id)
            _toast("Removed from watch list.")
        else:
            watchlist_ids.add(watch_id)
            _toast("Added to watch list.")
        st.session_state[watchlist_key] = watchlist_ids
        _set_query_params({"pos": position_filter, "view": view_choice})

elif add_param:
    try:
        add_id = int(add_param)
    except ValueError:
        add_id = None
    if add_id:
        add_player_obj = players_by_id.get(add_id)
        if add_player_obj and add_player_obj.get("availability") == "Owned":
            st.info("That player is already rostered.")
            _set_query_params({"pos": position_filter, "view": view_choice})
        else:
            team_choice_id = st.session_state.get("waiver_team_choice_id")
            if team_choice_id is None and league["teams"]:
                team_choice_id = league["teams"][0]["id"]
            if team_choice_id is not None:
                rosters[team_choice_id].append(add_id)
                st.session_state[rosters_key] = rosters
                if add_id in watchlist_ids:
                    watchlist_ids.remove(add_id)
                st.session_state[watchlist_key] = watchlist_ids
                _toast("Claim submitted.")
            _set_query_params({"pos": position_filter, "view": view_choice})

display_players = waiver_players if not watchlist_only else [p for p in waiver_players if p["id"] in watchlist_ids]
filtered = []
for player in display_players:
    if position_filter != "All" and player["pos"] != position_filter:
        continue
    if search_query and search_query.lower() not in player["name"].lower():
        continue
    filtered.append(player)

view_links = []
for key, label in view_label_map.items():
    view_query = urlencode({"pos": position_filter, "view": key})
    view_links.append(f'<a href="?{view_query}">{label}</a>')
current_query = urlencode({"pos": position_filter, "view": view_choice})
watch_header_html = "\n".join(
    [
        '<div class="watch-header">',
        '  <div class="watch-title">WATCH LIST</div>',
        '  <div class="watch-actions">',
        f'    <a class="watch-icon" href="?{current_query}">UP</a>',
        '    <details class="watch-dropdown">',
        f'      <summary>{view_label}</summary>',
        '      <div class="watch-dropdown-menu">',
        f"        {''.join(view_links)}",
        "      </div>",
        "    </details>",
        "  </div>",
        "</div>",
    ]
)
st.markdown(watch_header_html, unsafe_allow_html=True)
st.markdown('<div class="watch-divider"></div>', unsafe_allow_html=True)

if not filtered:
    st.info("No players match those filters.")
else:
    view_columns = {
        "matchup": ("PROJ", "SCORE"),
        "season": ("AVG", "PTS"),
        "proj": ("PROJ", "CEIL"),
        "last3": ("L3 AVG", "TREND"),
    }
    col_left, col_right = view_columns.get(view_choice, ("PROJ", "SCORE"))
    header = (
        '<div class="watch-header-row">'
        f"<div>Players</div><div>{col_left}</div><div>{col_right}</div>"
        "</div>"
    )
    rows_html = []
    for player in filtered[:50]:
        name_parts = player["name"].split()
        first_initial = name_parts[0][0] + "." if name_parts else ""
        last_name = name_parts[-1] if name_parts else player["name"]
        school = player.get("school") or player.get("team") or "Unknown"
        rost_pct = int(player["owned_pct"])
        delta = round(random.uniform(-5.5, 5.5), 1)
        delta_class = "trend-up" if delta >= 0 else "trend-down"
        delta_arrow = "↑" if delta >= 0 else "↓"
        bye_week = random.random() < 0.08
        if bye_week:
            matchup_line = '<span class="trend-down">BYE</span>'
        else:
            opp = random.choice(["ALA", "UGA", "OSU", "TEX", "LSU", "MICH"])
            opp_rank = random.randint(1, 25)
            opp_diff = "trend-up" if opp_rank > 12 else "trend-down"
            matchup_line = f"Sat 7:30 {'@' if random.random() > 0.5 else 'vs'} {opp} (<span class='{opp_diff}'>#{opp_rank}</span>)"

        has_ir = random.random() < 0.1
        ir_badge = '<span class="player-ir">IR</span>' if has_ir else ""
        proj = player["proj"]
        score = "--" if random.random() < 0.5 else f"{round(proj + random.uniform(-4, 4), 1)}"
        avg = player.get("avg", proj)
        last = player.get("last", proj)
        if view_choice == "season":
            col_left_val = f"{avg:.1f}"
            col_right_val = f"{last:.1f}"
        elif view_choice == "proj":
            ceil_val = round(proj + random.uniform(3.0, 7.0), 1)
            col_left_val = f"{proj:.1f}"
            col_right_val = f"{ceil_val:.1f}"
        elif view_choice == "last3":
            l3_avg = round(avg + random.uniform(-2.0, 2.0), 1)
            trend_val = f"{delta:+.1f}"
            col_left_val = f"{l3_avg:.1f}"
            col_right_val = trend_val
        else:
            col_left_val = f"{proj:.1f}"
            col_right_val = score

        availability = player.get("availability", "FA")
        is_watch = player["id"] in watchlist_ids
        add_disabled = availability == "Owned"
        action_param = "watch" if is_watch else "add"
        action_query = urlencode(
            {action_param: player["id"], "pos": position_filter, "view": view_choice}
        )
        action_class = "add-btn disabled" if add_disabled else "add-btn"
        action_label = "+"

        player_link = f"/Player?playerId={player['id']}"
        rows_html.append(
            "".join(
                [
                    f'<div class="watch-row" role="button" tabindex="0" ',
                    f'onclick="window.location.href=\'{player_link}\'">',
                    '<div class="player-left">',
                    f'<a class="{action_class}" href="?{action_query}" ',
                    'onclick="event.stopPropagation();">',
                    f"{action_label}</a>",
                    f'<div class="player-avatar">{first_initial}{last_name[:1]}{ir_badge}</div>',
                    f'<a class="player-link" href="{player_link}" ',
                    'onclick="event.stopPropagation();">',
                    f'<div class="player-name">{first_initial} {last_name}',
                    f'<span class="player-meta">{player["pos"]}</span>',
                    f"<span class=\"player-meta\">{school}</span>",
                    f'<span class="player-meta">{player.get("class_year", "Jr")}</span>',
                    '<span class="note-icon"></span>',
                    "</div>",
                    f'<div class="player-sub">{rost_pct}% Rost | ',
                    f'<span class="{delta_class}">{delta:+.1f} {delta_arrow}</span></div>',
                    f'<div class="player-matchup">{matchup_line}</div>',
                    "</a>",
                    "</div>",
                    f"<div>{col_left_val}</div>",
                    f"<div>{col_right_val}</div>",
                    "</div>",
                ]
            )
        )
    st.markdown(
        f'<div class="watch-list">{header}{"".join(rows_html)}</div>',
        unsafe_allow_html=True,
    )

st.markdown("")

right_col = st.container()
with right_col:
    st.subheader("Manage Roster")
    team_names = {team["name"]: team["id"] for team in league["teams"]}
    team_choice = st.selectbox("Team", list(team_names.keys()), key="waiver_team_choice")
    team_id = team_names[team_choice]
    st.session_state["waiver_team_choice_id"] = team_id

    roster_players = [player for player in players_pool if player["id"] in rosters.get(team_id, [])]
    roster_names = [player["name"] for player in roster_players]

    add_player = st.selectbox("Add from waiver wire", [player["name"] for player in waiver_players][:30])
    drop_player = st.selectbox("Drop from roster", roster_names if roster_names else ["None"])
    if st.button("Add / Drop"):
        add_obj = next((player for player in players_pool if player["name"] == add_player), None)
        drop_obj = next((player for player in roster_players if player["name"] == drop_player), None)
        if add_obj:
            rosters[team_id].append(add_obj["id"])
        if drop_obj:
            rosters[team_id].remove(drop_obj["id"])
        st.session_state[rosters_key] = rosters
        st.success("Roster updated.")
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

st.subheader("Live player stats (SportsDataIO)")
try:
    data = api_client.get_players()
    players_data = data["data"]
except Exception:
    players_data = []

if players_data:
    player_options = {f"{player['name']} (#{player['id']})": player for player in players_data}
    selected_player_label = st.selectbox("Select player", list(player_options.keys()))
    selected_player = player_options.get(selected_player_label)
    stats_col, refresh_col = st.columns([2, 1])
    with stats_col:
        season = st.number_input("Season", min_value=2000, max_value=2100, value=datetime.now().year, step=1)
        week = st.number_input("Week", min_value=1, max_value=20, value=1, step=1)
    with refresh_col:
        refresh = st.checkbox("Refresh from SportsDataIO", value=False)

    if selected_player:
        try:
            stats_response = api_client.get_player_stats(
                selected_player["id"], season=int(season), week=int(week), refresh=refresh
            )
            if stats_response.get("stats"):
                st.json(stats_response["stats"])
            else:
                message = stats_response.get("message") or "No stats available."
                st.info(message)
        except Exception as exc:
            st.error(f"Failed to load player stats: {exc}")
else:
    st.info("Load players to view live stats.")
