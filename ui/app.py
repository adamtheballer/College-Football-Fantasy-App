import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import html
import textwrap
import streamlit as st

from ui.lib.auth.fake_auth import use_session
from ui.lib.theme import apply_theme

st.set_page_config(page_title="Home", layout="wide")
apply_theme()

nav_keys = {"home", "leagues", "waiver", "settings"}
nav_param = None
try:
    nav_param = st.query_params.get("nav")
    if isinstance(nav_param, list):
        nav_param = nav_param[0]
except Exception:
    params = st.experimental_get_query_params()
    nav_param = params.get("nav", [None])[0]

if nav_param in nav_keys:
    st.session_state["nav"] = nav_param

current_nav = st.session_state.get("nav", "home")

session = use_session()
user_label = session["name"] if session else "Login"
login_href = "/Settings" if session else "/Login"

nav_items = [
    ("HOME", "home", "home"),
    ("LEAGUES", "leagues", "trophy"),
    ("WAIVER WIRE", "waiver", "users"),
    ("SETTINGS", "settings", "settings"),
]

sidebar_links = []
for label, key, icon in nav_items:
    active_class = " active" if current_nav == key else ""
    aria_current = ' aria-current="page"' if current_nav == key else ""
    sidebar_links.append(
        f'<a class="sidebar-link sidebar-link--{icon}{active_class}" href="?nav={key}"{aria_current}>'
        '<span class="sidebar-icon"></span>'
        f'<span class="sidebar-label">{label}</span>'
        "</a>"
    )

stat_cards = [
    {
        "icon": "trophy",
        "value": "4,821.5",
        "label": "SEASON POINTS",
        "trend": "↗ +12.4%",
        "trend_class": "up",
        "tone": "blue",
    },
    {
        "icon": "users",
        "value": "04",
        "label": "ACTIVE LEAGUES",
        "trend": "↗ +1 NEW",
        "trend_class": "up",
        "tone": "green",
    },
    {
        "icon": "heartbeat",
        "value": "84.2%",
        "label": "PLAYER EFFICIENCY",
        "trend": "↘ -2.1%",
        "trend_class": "down",
        "tone": "orange",
    },
    {
        "icon": "star",
        "value": "#1,284",
        "label": "GLOBAL RANK",
        "trend": "↗ +412",
        "trend_class": "up",
        "tone": "purple",
    },
]

icon_svgs = {
    "trophy": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M7 4h10v3a5 5 0 0 1-4 5v2h3v3H8v-3h3v-2a5 5 0 0 1-4-5V4z"/>'
        "</svg>"
    ),
    "users": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>'
        '<path d="M16 3.13a4 4 0 0 1 0 7.75"/>'
        "</svg>"
    ),
    "heartbeat": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 12h4l2-4 4 8 2-4h4"/>'
        "</svg>"
    ),
    "star": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 '
        '5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>'
        "</svg>"
    ),
}

stat_cards_html = []
for card in stat_cards:
    icon_svg = icon_svgs[card["icon"]]
    stat_cards_html.append(
        "".join(
            [
                f'<div class="stat-card stat-card--{card["tone"]}">',
                '<div class="stat-card__top">',
                f'<div class="stat-card__icon">{icon_svg}</div>',
                f'<div class="stat-card__trend stat-card__trend--{card["trend_class"]}">{card["trend"]}</div>',
                "</div>",
                f'<div class="stat-card__value">{card["value"]}</div>',
                f'<div class="stat-card__label">{card["label"]}</div>',
                "</div>",
            ]
        )
    )

css = """
<style>
html, body, [data-testid="stAppViewContainer"] {
    background: #070C16;
}

header, footer, [data-testid="stToolbar"], [data-testid="stDecoration"], #MainMenu {
    display: none !important;
    height: 0 !important;
    visibility: hidden !important;
}

[data-testid="stSidebar"] {
    display: none !important;
}

[data-testid="stAppViewContainer"] .block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

.app-shell {
    display: flex;
    min-height: 100vh;
    background: #070C16;
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

.sidebar {
    width: 420px;
    min-width: 420px;
    background: linear-gradient(180deg, #0A1425 0%, #0B1527 55%, #050A15 100%);
    border-right: 1px solid rgba(120, 170, 255, 0.08);
    box-shadow: inset -12px 0 24px rgba(40, 120, 255, 0.06);
    padding: 44px 26px 0 42px;
    box-sizing: border-box;
}

.sidebar-logo {
    font-size: 20px;
    font-weight: 800;
    font-style: italic;
    letter-spacing: 0.4px;
    color: #54A7FE;
    text-transform: uppercase;
}

.sidebar-nav {
    margin-top: 46px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.sidebar-link {
    display: flex;
    align-items: center;
    gap: 0;
    height: 58px;
    width: 300px;
    border-radius: 29px;
    padding-left: 18px;
    text-decoration: none;
    text-transform: uppercase;
    letter-spacing: 2.2px;
    font-size: 12px;
    font-weight: 800;
    color: #76869A;
    transition: background 160ms ease, color 160ms ease, transform 160ms ease;
}

.sidebar-link:hover {
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.07), rgba(255, 255, 255, 0.03));
    color: #E0E6EF;
    transform: translateY(-1px);
}

.sidebar-link:active {
    background: rgba(255, 255, 255, 0.09);
    transform: translateY(0);
}

.sidebar-link.active {
    background: #64B0FF;
    color: #232A3B;
    box-shadow: 0 10px 24px rgba(30, 120, 255, 0.18);
}

.sidebar-icon {
    width: 20px;
    height: 20px;
    margin-right: 12px;
    background-repeat: no-repeat;
    background-size: 20px 20px;
}

.sidebar-link--home .sidebar-icon {
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%2354A7FE' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M3 10.5L12 3l9 7.5'/><path d='M5 9.5V21h14V9.5'/></svg>");
}

.sidebar-link--trophy .sidebar-icon {
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%2354A7FE' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M8 21h8'/><path d='M12 17v4'/><path d='M7 4h10l2 5-3 4H8L5 9z'/></svg>");
}

.sidebar-link--users .sidebar-icon {
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%2354A7FE' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'/><circle cx='9' cy='7' r='4'/><path d='M23 21v-2a4 4 0 0 0-3-3.87'/><path d='M16 3.13a4 4 0 0 1 0 7.75'/></svg>");
}

.sidebar-link--settings .sidebar-icon {
    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%2354A7FE' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='3'/><path d='M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.2a1.7 1.7 0 0 0-1.5 1z'/></svg>");
}

.sidebar-link.active.sidebar-link--home .sidebar-icon,
.sidebar-link.active.sidebar-link--trophy .sidebar-icon,
.sidebar-link.active.sidebar-link--users .sidebar-icon,
.sidebar-link.active.sidebar-link--settings .sidebar-icon {
    filter: brightness(0.25);
}

.main {
    flex: 1;
    padding: 22px 54px 40px;
    background: radial-gradient(1100px 700px at 55% 8%, rgba(100, 176, 255, 0.12) 0%, rgba(7, 12, 22, 0) 55%),
        radial-gradient(900px 650px at 78% 65%, rgba(100, 176, 255, 0.08) 0%, rgba(7, 12, 22, 0) 60%),
        linear-gradient(180deg, #070C16 0%, #060B16 55%, #050A14 100%);
    box-sizing: border-box;
}

.top-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size: 10px;
    letter-spacing: 4px;
    color: rgba(100, 176, 255, 0.75);
    text-transform: uppercase;
}

.top-header a {
    font-size: 10px;
    letter-spacing: 3px;
    color: #8A97A8;
    text-decoration: none;
}

.top-divider {
    height: 1px;
    background: rgba(120, 170, 255, 0.1);
    margin-top: 16px;
    margin-bottom: 48px;
}

.overview-row {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 18px;
}

.overview-line {
    width: 30px;
    height: 2px;
    background: #64B0FF;
}

.overview-label {
    font-size: 10px;
    letter-spacing: 4px;
    color: rgba(100, 176, 255, 0.8);
    text-transform: uppercase;
}

.hero {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 32px;
}

.hero-title {
    font-size: 78px;
    font-weight: 900;
    font-style: italic;
    letter-spacing: -1px;
    line-height: 0.92;
    color: #F7FBFF;
    text-transform: uppercase;
    text-shadow: 0 14px 44px rgba(0, 0, 0, 0.55);
    max-width: 760px;
}

.hero-subtitle {
    font-size: 16px;
    line-height: 1.65;
    color: #8A97A8;
    max-width: 640px;
    margin-top: 18px;
    margin-bottom: 34px;
}

.hero-highlight {
    color: #64B0FF;
    font-style: italic;
    font-weight: 800;
}

.hero-right {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-top: 32px;
}

.session {
    text-align: right;
}

.session-label {
    font-size: 10px;
    letter-spacing: 3px;
    color: rgba(138, 151, 168, 0.55);
    text-transform: uppercase;
}

.session-value {
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #2EE59D;
    text-transform: uppercase;
    margin-top: 6px;
}

.season-pill {
    height: 34px;
    padding: 0 16px;
    border-radius: 999px;
    border: 1px solid rgba(120, 170, 255, 0.18);
    background: rgba(15, 30, 55, 0.3);
    color: #64B0FF;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    justify-content: center;
}

.hero-divider {
    height: 1px;
    background: rgba(120, 170, 255, 0.08);
    margin-top: 26px;
    margin-bottom: 28px;
}

.stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 22px;
}

.stat-card {
    height: 160px;
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(120, 170, 255, 0.1);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03), 0 22px 60px rgba(0, 0, 0, 0.45);
    padding: 18px;
    position: relative;
    box-sizing: border-box;
}

.stat-card__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.stat-card__icon {
    width: 42px;
    height: 42px;
    border-radius: 14px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #ffffff;
    box-shadow: 0 0 22px rgba(0, 0, 0, 0.35);
}

.stat-card--blue .stat-card__icon {
    background: linear-gradient(135deg, rgba(100, 176, 255, 0.95), rgba(59, 130, 246, 0.95));
    box-shadow: 0 0 18px rgba(100, 176, 255, 0.4);
}

.stat-card--green .stat-card__icon {
    background: linear-gradient(135deg, rgba(46, 229, 157, 0.9), rgba(16, 185, 129, 0.9));
    box-shadow: 0 0 18px rgba(46, 229, 157, 0.35);
}

.stat-card--orange .stat-card__icon {
    background: linear-gradient(135deg, rgba(255, 154, 31, 0.95), rgba(245, 158, 11, 0.95));
    box-shadow: 0 0 18px rgba(255, 154, 31, 0.35);
}

.stat-card--purple .stat-card__icon {
    background: linear-gradient(135deg, rgba(139, 92, 255, 0.95), rgba(99, 102, 241, 0.95));
    box-shadow: 0 0 18px rgba(139, 92, 255, 0.35);
}

.stat-card__icon svg {
    width: 20px;
    height: 20px;
    stroke: #ffffff;
}

.stat-card__trend {
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
}

.stat-card__trend--up {
    color: #2EE59D;
}

.stat-card__trend--down {
    color: #FF4D4D;
}

.stat-card__value {
    font-size: 32px;
    font-weight: 900;
    color: #EAF0F7;
    margin-top: 22px;
}

.stat-card__label {
    font-size: 10px;
    letter-spacing: 3px;
    font-weight: 800;
    color: rgba(138, 151, 168, 0.55);
    margin-top: 8px;
    text-transform: uppercase;
}

@media (max-width: 1200px) {
    .hero-title {
        font-size: 72px;
    }
    .stats-row {
        grid-template-columns: repeat(2, 1fr);
    }
}

@media (max-width: 900px) {
    .sidebar {
        display: none;
    }
    .main {
        padding: 20px 24px 32px;
    }
    .hero {
        flex-direction: column;
    }
    .hero-right {
        margin-top: 0;
        align-self: flex-start;
    }
}
</style>
"""

layout_html = "\n".join(
    [
        '<div class="app-shell">',
        '<aside class="sidebar">',
        '<div class="sidebar-logo">CFB FANTASY</div>',
        f'<nav class="sidebar-nav">{"".join(sidebar_links)}</nav>',
        "</aside>",
        '<main class="main">',
        '<div class="top-header">',
        "<div>College Football Fantasy</div>",
        f'<a href="{login_href}">{html.escape(user_label)}</a>',
        "</div>",
        '<div class="top-divider"></div>',
        '<div class="overview-row">',
        '<div class="overview-line"></div>',
        '<div class="overview-label">Dashboard Overview</div>',
        "</div>",
        '<div class="hero">',
        "<div>",
        '<div class="hero-title">College Football<br/>Fantasy</div>',
        '<div class="hero-subtitle">',
        'The ultimate platform for <span class="hero-highlight">College Football Enthusiasts.</span> '
        "Manage your roster, track live scores, and dominate your league.",
        "</div>",
        "</div>",
        '<div class="hero-right">',
        '<div class="session">',
        '<div class="session-label">Session Status</div>',
        '<div class="session-value">Live &bull; Active</div>',
        "</div>",
        '<div class="season-pill">2024 Season</div>',
        "</div>",
        "</div>",
        '<div class="hero-divider"></div>',
        f'<div class="stats-row">{"".join(stat_cards_html)}</div>',
        "</main>",
        "</div>",
    ]
)

st.markdown(textwrap.dedent(css) + layout_html, unsafe_allow_html=True)
