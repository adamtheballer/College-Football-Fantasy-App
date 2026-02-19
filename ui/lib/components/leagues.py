from __future__ import annotations

import streamlit as st

from ui.lib.team_branding import team_logo_html


def render_league_row(league: dict, on_jump) -> None:
    with st.container(border=True):
        left_col, mid_col, right_col = st.columns([2.3, 2.7, 1])
        with left_col:
            st.markdown(f"**{league['name']}**")
            st.caption(f"Week {league['current_week']} · {league['team_count']} teams")
        with mid_col:
            st.caption("Standings preview")
            preview_lines = []
            for entry in league.get("standings_preview", []):
                preview_lines.append(
                    f"{entry['rank']}. {team_logo_html(entry['team'])} {entry['team']} ({entry['record']})"
                )
            if preview_lines:
                st.markdown("\n".join(f"- {line}" for line in preview_lines), unsafe_allow_html=True)
            else:
                st.caption("No standings available.")
        with right_col:
            if st.button("Jump to League", key=f"jump_{league['id']}"):
                on_jump(league["id"])
