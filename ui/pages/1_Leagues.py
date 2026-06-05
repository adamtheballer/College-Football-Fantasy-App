import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.theme import apply_theme

st.header("Leagues")
apply_theme()

st.warning(
    "The Streamlit league page is legacy/dev-only and is intentionally disabled. "
    "Use the React web app for league creation and settings so roster, scoring, and draft settings persist through the current FastAPI schema."
)
st.info(
    "Run the React frontend and create leagues at /leagues/create. "
    "This avoids sending the old flat league payload that no longer matches the nested league creation API."
)
