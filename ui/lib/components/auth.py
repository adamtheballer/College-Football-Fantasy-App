from __future__ import annotations

import streamlit as st

from ui.lib.auth.fake_auth import logout, use_session


def render_auth_controls() -> None:
    session = use_session()
    if not session:
        if st.button("Login"):
            if hasattr(st, "switch_page"):
                st.switch_page("pages/7_Login.py")
            else:
                st.info("Open the Login page from the sidebar to continue.")
        return

    menu = st.selectbox(
        session["name"],
        ["Profile", "Settings", "Logout"],
        label_visibility="collapsed",
    )
    if menu == "Settings":
        if hasattr(st, "switch_page"):
            st.switch_page("pages/6_Settings.py")
    elif menu == "Logout":
        logout()
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()
