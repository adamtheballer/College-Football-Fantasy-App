import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import streamlit as st

from ui.lib.components.sidebar import render_sidebar_nav
from ui.lib.components.top_nav import render_top_nav
from ui.lib.preferences import load_preferences, save_preferences
from ui.lib.theme import apply_theme

st.set_page_config(page_title="Settings", layout="wide")
apply_theme()
render_sidebar_nav("settings")
render_top_nav("auth")

st.markdown(
    """
    <style>
    .settings-shell {
        max-width: 900px;
        margin: 0 auto;
        padding-bottom: 2rem;
    }

    .settings-card {
        background: #121820;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 16px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    .settings-title {
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.08rem;
        color: #8fa0b6;
        margin-bottom: 0.6rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _rerun() -> None:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


prefs = load_preferences()

st.markdown('<div class="settings-shell">', unsafe_allow_html=True)
st.title("Settings")
st.caption("Update your preferences and ESPN-style theme selection.")

with st.form("settings_form"):
    st.markdown('<div class="settings-card"><div class="settings-title">Notifications</div>', unsafe_allow_html=True)
    injury_alerts = st.checkbox("Injury alerts", value=prefs["notifications"]["injury_alerts"])
    lineup_reminders = st.checkbox("Lineup reminders", value=prefs["notifications"]["lineup_reminders"])
    trade_alerts = st.checkbox("Trade alerts", value=prefs["notifications"]["trade_alerts"])
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="settings-card"><div class="settings-title">Preferences</div>', unsafe_allow_html=True)
    team_options = [
        "Alabama",
        "Georgia",
        "Ohio State",
        "Michigan",
        "Texas",
        "Oregon",
        "USC",
        "LSU",
        "Florida State",
        "Clemson",
    ]
    favorite_team = st.selectbox(
        "Favorite team",
        team_options,
        index=team_options.index(prefs.get("favorite_team", "Alabama")),
    )
    theme_options = ["ESPN", "Light", "Dark", "System"]
    theme_choice = st.selectbox(
        "Theme",
        theme_options,
        index=theme_options.index(prefs.get("theme", "ESPN")),
    )
    st.markdown("</div>", unsafe_allow_html=True)

    saved = st.form_submit_button("Save settings")

if saved:
    updated = {
        "theme": theme_choice,
        "favorite_team": favorite_team,
        "notifications": {
            "injury_alerts": injury_alerts,
            "lineup_reminders": lineup_reminders,
            "trade_alerts": trade_alerts,
        },
    }
    save_preferences(updated)
    st.success("Settings saved.")
    _rerun()

st.markdown("</div>", unsafe_allow_html=True)
