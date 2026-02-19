from __future__ import annotations

import streamlit as st

def render_sidebar_nav(current: str) -> None:
    nav_items = [
        ("Home", "app.py", "home"),
        ("Leagues", "pages/1_Leagues.py", "leagues"),
        ("Waiver Wire", "pages/4_Players.py", "players"),
        ("Settings", "pages/6_Settings.py", "settings"),
    ]

    st.sidebar.markdown("**CFB Fantasy**")
    st.sidebar.markdown('<div class="sidebar-nav">', unsafe_allow_html=True)
    for label, target, key in nav_items:
        disabled = current == key
        if st.sidebar.button(label, key=f"nav_{key}", disabled=disabled):
            if hasattr(st, "switch_page"):
                st.switch_page(target)
            else:
                st.sidebar.info("Use the sidebar to switch pages.")
    st.sidebar.markdown("</div>", unsafe_allow_html=True)
