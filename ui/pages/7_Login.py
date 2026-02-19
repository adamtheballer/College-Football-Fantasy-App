import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.auth.fake_auth import login, use_session
from ui.lib.components.sidebar import render_sidebar_nav
from ui.lib.components.top_nav import render_top_nav
from ui.lib.theme import apply_theme

st.set_page_config(page_title="Login", layout="wide")
apply_theme()
render_sidebar_nav("auth")
render_top_nav("auth")

st.markdown(
    """
    <style>
    .login-shell {
        max-width: 520px;
        margin: 0 auto;
        padding-top: 2rem;
    }

    .login-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

session = use_session()
if session:
    st.success(f"You're already signed in as {session['name']}.")
    if st.button("Go to Home"):
        if hasattr(st, "switch_page"):
            st.switch_page("app.py")
        else:
            st.info("Open the Home page from the sidebar.")
    st.stop()

st.markdown('<div class="login-shell">', unsafe_allow_html=True)
st.title("Sign in")
st.caption("Use any email/password for the mock login.")

with st.form("login_form"):
    email = st.text_input("Email", value="adam@example.com")
    password = st.text_input("Password", type="password")
    remember = st.checkbox("Remember me", value=True)
    submitted = st.form_submit_button("Sign in")

if submitted:
    login(email=email, remember=remember)
    st.success("Signed in.")
    if hasattr(st, "switch_page"):
        st.switch_page("app.py")
    else:
        st.info("Open the Home page from the sidebar.")

st.markdown("</div>", unsafe_allow_html=True)
