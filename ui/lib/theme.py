import streamlit as st

from ui.lib.preferences import load_preferences


def apply_theme() -> None:
    prefs = load_preferences()
    theme_choice = prefs.get("theme", "ESPN")
    system_override = ""
    if theme_choice == "Light":
        root_vars = """
            --bg-main: #f5f6f8;
            --bg-surface: #ffffff;
            --bg-surface-2: #eef1f6;
            --text-primary: #1b1f24;
            --text-secondary: #4c5666;
            --accent-green: #0f9d58;
            --accent-blue: #00529b;
            --accent-muted: #e1e6ef;
            --status-danger: #d93025;
            --border-subtle: #d7dde7;
            --border-strong: #c5ceda;
            --radius-lg: 12px;
            --radius-xl: 16px;
            --chalk: #1b1f24;
            --playbook-line: rgba(0, 0, 0, 0.06);
            --playbook-line-soft: rgba(0, 0, 0, 0.035);
            --paper-tint: rgba(255, 255, 255, 0.7);
        """
        app_bg = "linear-gradient(180deg, #f5f6f8 0%, #e9edf3 100%)"
    elif theme_choice == "Dark":
        root_vars = """
            --bg-main: #0b0f14;
            --bg-surface: #141a22;
            --bg-surface-2: #1f2833;
            --text-primary: #f5f5f5;
            --text-secondary: #b0b0b0;
            --accent-green: #2ed158;
            --accent-blue: #4aa3ff;
            --accent-muted: #2a3340;
            --status-danger: #ff5b5b;
            --border-subtle: #303a48;
            --border-strong: #3a4556;
            --radius-lg: 12px;
            --radius-xl: 16px;
            --chalk: #cfd8e6;
            --playbook-line: rgba(255, 255, 255, 0.05);
            --playbook-line-soft: rgba(255, 255, 255, 0.03);
            --paper-tint: rgba(255, 255, 255, 0.05);
        """
        app_bg = "linear-gradient(180deg, #0b0f14 0%, #121820 100%)"
    elif theme_choice == "System":
        root_vars = """
            --bg-main: #f5f6f8;
            --bg-surface: #ffffff;
            --bg-surface-2: #eef1f6;
            --text-primary: #1b1f24;
            --text-secondary: #4c5666;
            --accent-green: #0f9d58;
            --accent-blue: #00529b;
            --accent-muted: #e1e6ef;
            --status-danger: #d93025;
            --border-subtle: #d7dde7;
            --border-strong: #c5ceda;
            --radius-lg: 12px;
            --radius-xl: 16px;
            --chalk: #1b1f24;
            --playbook-line: rgba(0, 0, 0, 0.06);
            --playbook-line-soft: rgba(0, 0, 0, 0.035);
            --paper-tint: rgba(255, 255, 255, 0.7);
        """
        app_bg = "linear-gradient(180deg, #f5f6f8 0%, #e9edf3 100%)"
        system_override = """
        @media (prefers-color-scheme: dark) {
            :root {
                --bg-main: #0b0f14;
                --bg-surface: #141a22;
                --bg-surface-2: #1f2833;
                --text-primary: #f5f5f5;
                --text-secondary: #b0b0b0;
                --accent-green: #2ed158;
                --accent-blue: #4aa3ff;
                --accent-muted: #2a3340;
                --status-danger: #ff5b5b;
                --border-subtle: #303a48;
                --border-strong: #3a4556;
                --chalk: #cfd8e6;
                --playbook-line: rgba(255, 255, 255, 0.05);
                --playbook-line-soft: rgba(255, 255, 255, 0.03);
                --paper-tint: rgba(255, 255, 255, 0.05);
            }
            html, body, [data-testid="stAppViewContainer"] {
                background: linear-gradient(180deg, #0b0f14 0%, #121820 100%);
            }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, #0b0f14 0%, #121820 100%);
            }
        }
        """
    else:
        root_vars = """
            --bg-main: #0a0d12;
            --bg-surface: #12161d;
            --bg-surface-2: #1c2330;
            --text-primary: #f5f5f5;
            --text-secondary: #b0b0b0;
            --accent-green: #c41230;
            --accent-blue: #4aa3ff;
            --accent-muted: #242c38;
            --status-danger: #ff5b5b;
            --border-subtle: #2d3746;
            --border-strong: #3b4658;
            --radius-lg: 12px;
            --radius-xl: 16px;
            --chalk: #d6dfeb;
            --playbook-line: rgba(255, 255, 255, 0.05);
            --playbook-line-soft: rgba(255, 255, 255, 0.03);
            --paper-tint: rgba(255, 255, 255, 0.06);
        """
        app_bg = (
            "linear-gradient(150deg, #0a0f16 0%, #0f1724 45%, #0a0f16 100%),"
            "radial-gradient(circle at 12% 18%, rgba(255, 255, 255, 0.06) 0%, transparent 55%),"
            "repeating-linear-gradient(0deg, rgba(255, 255, 255, 0.035) 0 1px, transparent 1px 34px),"
            "repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.025) 0 1px, transparent 1px 34px)"
        )
        system_override = ""

    css = """
        <style>
        :root {
            __ROOT_VARS__
        }

        html, body, [data-testid="stAppViewContainer"] {
            background: __APP_BG__;
            color: var(--text-primary);
            font-family: "Avenir Next", "Gill Sans", "Trebuchet MS", sans-serif;
            background-attachment: fixed;
            background-size: auto, auto, 34px 34px, 34px 34px;
            background-position: center, center, top left, top left;
        }

        [data-testid="stSidebar"] {
            background: __APP_BG__;
            border-right: 1px solid var(--border-subtle);
            background-size: auto, auto, 34px 34px, 34px 34px;
        }

        body::before {
            content: "";
            position: fixed;
            inset: 0;
            background-image:
                radial-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
                radial-gradient(rgba(0, 0, 0, 0.08) 1px, transparent 1px);
            background-size: 3px 3px, 5px 5px;
            opacity: 0.2;
            pointer-events: none;
            mix-blend-mode: soft-light;
            z-index: 0;
        }

        [data-testid="stAppViewContainer"] > .main {
            position: relative;
            z-index: 1;
        }

        .top-nav {
            position: sticky;
            top: 0;
            z-index: 60;
            background: linear-gradient(180deg, rgba(20, 26, 34, 0.92) 0%, rgba(12, 16, 22, 0.92) 100%);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 0.4rem 0.6rem;
            margin: 0.6rem 0 1rem;
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.35);
        }

        .top-nav-title {
            font-size: 1.15rem;
            font-weight: 800;
            letter-spacing: 0.03rem;
            color: #f3f6ff;
            margin: 0.2rem 0 0.4rem;
            text-transform: uppercase;
            font-family: "Bebas Neue", "Oswald", "Arial Narrow", sans-serif;
        }

        .top-nav button {
            width: 100%;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.14);
            color: #d6dfeb;
            font-weight: 700;
            letter-spacing: 0.04rem;
            text-transform: uppercase;
            font-size: 0.65rem;
            padding: 0.35rem 0.4rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .top-nav button:hover:not(:disabled) {
            border-color: rgba(255, 255, 255, 0.4);
            color: #f3f6ff;
            background: rgba(255, 255, 255, 0.12);
        }

        .top-nav button:disabled {
            background: rgba(255, 255, 255, 0.12);
            border-color: rgba(255, 255, 255, 0.4);
            color: #f3f6ff;
            opacity: 1;
        }

        [data-testid="stSidebarNav"] {
            display: none;
        }

        .sidebar-nav {
            display: flex;
            flex-direction: column;
            gap: 0.35rem;
            margin-top: 0.6rem;
        }

        .sidebar-nav button {
            width: 100%;
            text-align: left;
            padding: 0.45rem 0.8rem;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: #d6dfeb;
            font-weight: 600;
            letter-spacing: 0.02rem;
        }

        .sidebar-nav button:hover:not(:disabled) {
            border-color: rgba(255, 255, 255, 0.4);
            background: rgba(255, 255, 255, 0.1);
            color: #f1f5ff;
        }

        .sidebar-nav button:disabled {
            background: rgba(255, 255, 255, 0.12);
            border-color: rgba(255, 255, 255, 0.4);
            color: #f3f6ff;
            opacity: 1;
            cursor: default;
        }

        h1, h2, h3, h4, h5, h6 {
            color: var(--text-primary);
            font-weight: 700;
            letter-spacing: 0.2px;
        }

        h1, h2, h3 {
            font-family: "Bebas Neue", "Oswald", "Arial Narrow", sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.08rem;
            background: linear-gradient(90deg, #f3f6ff 0%, #c9d6e8 60%, #f3f6ff 100%);
            -webkit-background-clip: text;
            color: transparent;
        }

        .stMarkdown, .stText, .stTextInput label, .stSelectbox label, .stNumberInput label {
            color: var(--text-secondary);
        }

        div[data-baseweb="input"] > div {
            background-color: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            color: var(--text-primary);
        }

        textarea, input, select {
            color: var(--text-primary);
        }

        [data-baseweb="tab-list"] {
            border-bottom: 1px solid var(--border-subtle);
        }

        [data-baseweb="tab"] {
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-secondary);
            font-weight: 600;
        }

        [data-baseweb="tab"][aria-selected="true"] {
            color: var(--text-primary);
        }

        [data-baseweb="tab-highlight"] {
            background-color: var(--accent-green);
            height: 3px;
        }

        .stButton > button, .stDownloadButton > button {
            background-color: rgba(255, 255, 255, 0.06);
            color: #f3f6ff;
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 999px;
            padding: 0.45rem 1rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stButton > button:hover {
            background-color: rgba(255, 255, 255, 0.12);
            border-color: rgba(255, 255, 255, 0.35);
        }

        [data-testid="stForm"] {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-xl);
            padding: 1rem 1.2rem;
        }

        .stDataFrame {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-xl);
        }

        :is(
            .dashboard-card,
            .team-card,
            .news-card,
            .transactions-card,
            .draft-card,
            .schedule-card,
            .myteam-card,
            .trade-card,
            .waiver-card,
            .settings-card,
            .login-card,
            .player-card,
            .side-card,
            .public-card,
            .watch-list
        ) {
            background: linear-gradient(180deg, rgba(19, 24, 32, 0.95) 0%, rgba(13, 18, 25, 0.95) 100%) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.45);
            position: relative;
            overflow: hidden;
        }

        :is(
            .dashboard-card,
            .team-card,
            .news-card,
            .transactions-card,
            .draft-card,
            .schedule-card,
            .myteam-card,
            .trade-card,
            .waiver-card,
            .settings-card,
            .login-card,
            .player-card,
            .side-card,
            .public-card,
            .watch-list
        )::before {
            content: "";
            position: absolute;
            inset: 0;
            background-image:
                repeating-linear-gradient(0deg, rgba(255, 255, 255, 0.04) 0 1px, transparent 1px 28px),
                repeating-linear-gradient(90deg, rgba(255, 255, 255, 0.02) 0 1px, transparent 1px 28px);
            opacity: 0.22;
            pointer-events: none;
        }

        :is(
            .dashboard-card__header,
            .player-card-title,
            .settings-title,
            .myteam-title,
            .trade-title,
            .waiver-title,
            .draft-title,
            .public-title,
            .section-header__title
        ) {
            font-family: "Oswald", "Arial Narrow", sans-serif;
            text-transform: uppercase;
            letter-spacing: 0.08rem;
            color: var(--chalk);
        }

        .stAlert {
            border-radius: 12px;
        }

        .pos-qb { background: #ffb3ba; color: #333333; }
        .pos-rb { background: #baffc9; color: #333333; }
        .pos-wr { background: #bae1ff; color: #333333; }
        .pos-te { background: #ffffba; color: #333333; }
        .pos-k { background: #e1baff; color: #333333; }

        .queue-btn {
            background: #333333;
            border: 1px solid #555555;
            color: #ffffff;
            border-radius: 20px;
            padding: 8px 16px;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all 0.2s ease;
        }

        .queue-btn:hover {
            background: #444444;
            border-color: #666666;
        }

        .bottom-nav {
            background: linear-gradient(180deg, #000000 0%, #1a1a1a 100%);
            border-top: 1px solid #333333;
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 50;
            padding-bottom: env(safe-area-inset-bottom);
        }

        .draft-pick {
            background: #2a2a2a;
            border-radius: 8px;
            border: 1px solid #444444;
            position: relative;
        }

        .draft-pick.active {
            border-color: #007bff;
            box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.2);
        }

        .draft-pick.user-pick {
            background: #4caf50;
            border-color: #4caf50;
        }

        .player-row {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            position: relative;
        }

        .player-row:hover {
            transform: translateY(-4px) scale(1.02);
            background: rgba(255, 255, 255, 0.08);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(76, 175, 80, 0.3);
            border-radius: 12px;
            z-index: 10;
        }

        .player-name {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .player-row:hover .player-name {
            color: #4caf50;
            font-weight: 700;
            text-shadow: 0 0 8px rgba(76, 175, 80, 0.5);
            transform: translateY(-1px);
        }

        .roster-slot {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid #333333;
            border-radius: 8px;
            margin: 2px 0;
            transition: all 0.2s ease;
        }

        .roster-slot:hover {
            background: rgba(255, 255, 255, 0.05);
            border-color: #555555;
        }

        .roster-slot.filled {
            background: rgba(76, 175, 80, 0.1);
            border-color: #4caf50;
        }

        .roster-slot.empty {
            border-style: dashed;
            border-color: #555555;
            background: rgba(255, 255, 255, 0.01);
        }

        ::-webkit-scrollbar {
            width: 6px;
        }

        ::-webkit-scrollbar-track {
            background: #1a1a1a;
        }

        ::-webkit-scrollbar-thumb {
            background: #333333;
            border-radius: 3px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: #444444;
        }

        .draft-timer {
            font-family: "Courier New", monospace;
            font-weight: bold;
            letter-spacing: 1px;
        }

        .draft-timer.urgent {
            color: #ff4444;
            animation: pulse 1s infinite;
        }

        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin: 0.8rem 0 0.6rem;
        }

        .section-header__title {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.12rem;
            color: var(--text-secondary);
            font-weight: 700;
        }

        .section-header__meta {
            font-size: 0.7rem;
            color: var(--text-secondary);
        }

        .stat-pill {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 999px;
            background: var(--accent-muted);
            border: 1px solid var(--border-subtle);
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.08rem;
            color: var(--text-secondary);
            font-weight: 700;
        }

        .stat-pill.primary {
            background: rgba(0, 82, 155, 0.2);
            border-color: rgba(0, 82, 155, 0.4);
            color: #cfe1ff;
        }

        .stat-pill.accent {
            background: rgba(196, 18, 48, 0.2);
            border-color: rgba(196, 18, 48, 0.4);
            color: #ffb8c2;
        }

        .team-logo {
            width: 32px;
            height: 32px;
            border-radius: 10px;
            background: var(--accent-blue);
            color: #ffffff;
            font-weight: 700;
            font-size: 0.7rem;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            text-transform: uppercase;
        }

        .data-table {
            border: 1px solid var(--border-subtle);
            border-radius: var(--radius-lg);
            overflow: hidden;
        }

        .data-table__row {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 0.4rem;
            padding: 0.4rem 0.6rem;
            border-bottom: 1px solid var(--border-subtle);
            font-size: 0.75rem;
        }

        .data-table__row:last-child {
            border-bottom: none;
        }

        .data-table__row.header {
            text-transform: uppercase;
            letter-spacing: 0.08rem;
            font-size: 0.62rem;
            color: var(--text-secondary);
        }

        __SYSTEM_OVERRIDE__

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        </style>
        """
    css = (
        css.replace("__ROOT_VARS__", root_vars)
        .replace("__APP_BG__", app_bg)
        .replace("__SYSTEM_OVERRIDE__", system_override)
    )
    st.markdown(css, unsafe_allow_html=True)
