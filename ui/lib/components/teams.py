from __future__ import annotations

import streamlit as st

from ui.lib.team_branding import team_logo_html


def render_team_card(league_id: int, team: dict, on_view) -> None:
    starters = team.get("roster_summary", {}).get("starters", 0)
    bench = team.get("roster_summary", {}).get("bench", 0)
    ir = team.get("roster_summary", {}).get("ir", 0)

    with st.container(border=True):
        header_left, header_right = st.columns([3, 1])
        header_left.markdown(
            f"{team_logo_html(team['name'])} **{team['name']}**",
            unsafe_allow_html=True,
        )
        header_right.caption(team["record"])
        st.caption(team["owner"])
        meta_left, meta_right = st.columns(2)
        meta_left.caption(f"PF {team['points_for']}")
        meta_right.caption(f"Roster {starters}/{bench}/{ir}")
        if st.button("View Team", key=f"team_view_{league_id}_{team['id']}"):
            on_view(team["id"])
