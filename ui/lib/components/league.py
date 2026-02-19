from __future__ import annotations

import streamlit as st


def render_league_header(league: dict, week: int, week_options: list[int]) -> int:
    left_col, mid_col, right_col = st.columns([2.4, 1.2, 1])
    with left_col:
        st.markdown(f"## {league['name']}")
        st.caption(f"League #{league['id']} · {len(league['teams'])} teams")
    with mid_col:
        selected_week = st.selectbox("Week", week_options, index=week_options.index(week))
    with right_col:
        if league.get("commissioner"):
            st.markdown('<span class="commissioner-pill">Commissioner</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="commissioner-pill neutral">Member</span>', unsafe_allow_html=True)
    return selected_week


def render_league_tabs(tabs: list[str], active_tab: str) -> str:
    index = tabs.index(active_tab) if active_tab in tabs else 0
    selection = st.radio(
        "League Tabs",
        tabs,
        index=index,
        horizontal=True,
        key="league_tabs",
        label_visibility="collapsed",
    )
    return selection
