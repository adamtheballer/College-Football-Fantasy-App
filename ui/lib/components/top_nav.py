from __future__ import annotations

import streamlit as st

from ui.lib.auth.fake_auth import use_session


def render_top_nav(current: str) -> None:
    session = use_session()
    user_label = session["name"] if session else "Login"

    league_id = st.session_state.get("selected_league_id")
    team_id = st.session_state.get("selected_team_id")

    nav_items = [
        (user_label, "auth"),
        ("My Team", "team"),
        ("Matchup", "matchup"),
        ("Waiver Wire", "players"),
        ("League", "league"),
        ("Scoreboard", "scoreboard"),
    ]

    st.markdown(
        '<div class="top-nav-title">College Football Fantasy</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="top-nav">', unsafe_allow_html=True)
    cols = st.columns([1.1, 1.2, 1.1, 1.35, 0.95, 1.3])
    for col, (label, key) in zip(cols, nav_items):
        with col:
            disabled = current == key
            if st.button(label, key=f"topnav_{key}", disabled=disabled):
                if key == "auth":
                    if session:
                        if hasattr(st, "switch_page"):
                            st.switch_page("pages/6_Settings.py")
                    else:
                        if hasattr(st, "switch_page"):
                            st.switch_page("pages/7_Login.py")
                elif key == "players":
                    if hasattr(st, "switch_page"):
                        st.switch_page("pages/4_Players.py")
                elif key == "team":
                    if team_id and hasattr(st, "switch_page"):
                        st.switch_page("pages/3_Team.py")
                    elif hasattr(st, "switch_page"):
                        st.switch_page("pages/1_Leagues.py")
                elif key in {"matchup", "league", "scoreboard"}:
                    target_tab = "Matchup" if key == "matchup" else "Schedule" if key == "scoreboard" else "Standings"
                    st.session_state["nav_target_tab"] = target_tab
                    if league_id:
                        st.session_state["selected_league_id"] = league_id
                        if hasattr(st, "switch_page"):
                            st.switch_page("pages/2_League.py")
                    elif hasattr(st, "switch_page"):
                        st.switch_page("pages/1_Leagues.py")

    st.markdown("</div>", unsafe_allow_html=True)
