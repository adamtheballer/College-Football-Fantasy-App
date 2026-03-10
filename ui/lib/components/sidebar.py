from __future__ import annotations

import streamlit as st


def render_sidebar_nav(current: str) -> None:
    nav_items = [
        ("HOME", "/", "home", "home"),
        ("LEAGUES", "/Leagues", "leagues", "trophy"),
        ("WAIVER WIRE", "/Players", "players", "users"),
        ("SETTINGS", "/Settings", "settings", "settings"),
    ]

    st.sidebar.markdown('<div class="sidebar-title">CFB FANTASY</div>', unsafe_allow_html=True)
    links = []
    for label, href, key, icon in nav_items:
        active_class = " active" if current == key else ""
        aria_current = ' aria-current="page"' if current == key else ""
        links.append(
            (
                f'<a class="sidebar-link sidebar-link--{icon}{active_class}" '
                f'href="{href}"{aria_current}>'
                '<span class="sidebar-icon"></span>'
                f'<span class="sidebar-label">{label}</span>'
                "</a>"
            )
        )
    st.sidebar.markdown(
        f'<nav class="sidebar-nav" aria-label="Primary">{"".join(links)}</nav>',
        unsafe_allow_html=True,
    )
