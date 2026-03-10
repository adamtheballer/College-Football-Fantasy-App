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
            --bg-main: #030710;
            --bg-surface: rgba(10, 21, 37, 0.8);
            --bg-surface-2: rgba(8, 18, 34, 0.9);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-green: #34d399;
            --accent-blue: #38bdf8;
            --accent-muted: rgba(14, 165, 233, 0.12);
            --status-danger: #f87171;
            --border-subtle: rgba(21, 32, 53, 0.9);
            --border-strong: rgba(28, 45, 72, 0.9);
            --radius-lg: 12px;
            --radius-xl: 16px;
            --chalk: #f8fafc;
            --playbook-line: rgba(148, 163, 184, 0.2);
            --playbook-line-soft: rgba(148, 163, 184, 0.1);
            --paper-tint: rgba(14, 165, 233, 0.04);
        """
        app_bg = "linear-gradient(135deg, #030710 0%, #081222 45%, #0E1D35 100%)"
        system_override = ""

    css = """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        :root {
            __ROOT_VARS__
            --page-pad: 32px;
            --header-pad-x: 48px;
        }

        html, body, [data-testid="stAppViewContainer"] {
            background: __APP_BG__;
            color: var(--text-primary);
            font-family: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-variant-numeric: tabular-nums;
            background-attachment: fixed;
            background-size: auto, auto, auto, auto, auto;
            background-position: center, center, center, center, center;
            background-blend-mode: normal, normal, normal, normal, normal;
        }

        .main .block-container {
            padding: 0 var(--page-pad) 64px;
            max-width: none;
        }

        .main {
            background: linear-gradient(135deg, #030710 0%, #081222 45%, #0E1D35 100%);
            min-height: 100vh;
        }

        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        #MainMenu {
            display: none !important;
            height: 0 !important;
            visibility: hidden !important;
        }

        [data-testid="collapsedControl"],
        [data-testid="collapsedControlButton"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="stSidebarCollapseButton"],
        button[title*="sidebar"],
        button[aria-label*="sidebar"] {
            display: none !important;
        }

        [data-testid="stSidebar"] {
            width: 256px;
            min-width: 256px;
            background: linear-gradient(135deg, #030710 0%, #07101E 55%, #0C1628 100%);
            border-right: 1px solid rgba(17, 28, 48, 0.8);
            box-shadow: none;
        }

        [data-testid="stSidebar"] > div:first-child {
            padding: 0;
        }

        [data-testid="stSidebarResizer"] {
            display: none !important;
        }

        .top-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 32px;
            border-bottom: 1px solid rgba(30, 41, 59, 0.2);
            background: linear-gradient(90deg, transparent, rgba(13, 21, 41, 0.5), transparent);
            position: relative;
            margin-bottom: 32px;
        }

        .top-header::after {
            content: "";
            position: absolute;
            left: 0;
            right: 0;
            bottom: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.3), transparent);
        }

        .top-header-title {
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.25em;
            color: #94a3b8;
            text-transform: uppercase;
            white-space: nowrap;
        }

        .top-header-login-link {
            color: #94a3b8;
            font-size: 0.75rem;
            letter-spacing: 0.25em;
            text-transform: uppercase;
            text-decoration: none;
            font-weight: 600;
            transition: color 200ms ease;
            white-space: nowrap;
        }

        .top-header-login-link:hover {
            color: #ffffff;
        }

        .top-nav {
            position: sticky;
            top: 0;
            z-index: 50;
            background: rgba(10, 16, 26, 0.8);
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding: 0.5rem 0 0.7rem;
            margin-bottom: 1rem;
            backdrop-filter: blur(12px);
        }

        .top-nav button {
            width: 100%;
            border-radius: 999px;
            background: transparent;
            border: none;
            color: #9fb0c7;
            font-weight: 700;
            letter-spacing: 0.22em;
            text-transform: uppercase;
            font-size: 0.6rem;
            padding: 0.35rem 0.2rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            transition: all 0.2s ease;
            box-shadow: none;
        }

        .top-nav button:hover:not(:disabled) {
            color: #e5efff;
            background: transparent;
            transform: translateY(-1px);
        }

        .top-nav button:disabled {
            background: transparent;
            color: #f3f7ff;
            opacity: 1;
            box-shadow: inset 0 -2px 0 rgba(92, 167, 255, 0.9);
        }

        [data-testid="stSidebarNav"] {
            display: none;
        }

        .sidebar-nav {
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin-top: 24px;
            padding: 0 20px;
            align-items: stretch;
        }

        .sidebar-title {
            font-size: 20px;
            font-weight: 800;
            letter-spacing: -0.02em;
            margin: 0 0 0 28px;
            text-transform: uppercase;
            font-style: italic;
            color: #38bdf8;
        }

        .sidebar-link {
            display: flex;
            align-items: center;
            gap: 14px;
            color: #0369a1;
            text-decoration: none !important;
            text-transform: uppercase;
            letter-spacing: 0.2em;
            font-size: 11px;
            font-weight: 500;
            transition: color 200ms ease, background 200ms ease;
            width: 100%;
            padding: 12px 20px;
            border-radius: 999px;
            box-sizing: border-box;
            cursor: pointer;
            border-bottom: none;
            position: relative;
            line-height: 1.1;
        }

        .sidebar-label {
            text-decoration: none !important;
            border-bottom: none !important;
        }

        .sidebar-link:hover {
            color: #0ea5e9;
        }

        .sidebar-link.active {
            color: #0A1225;
            font-weight: 600;
            background: rgba(56, 189, 248, 0.75);
        }

        .sidebar-icon {
            width: 16px;
            height: 16px;
            flex: 0 0 16px;
            background-repeat: no-repeat;
            background-size: 16px 16px;
        }

        .sidebar-link--home .sidebar-icon {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230369a1' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M3 10.5L12 3l9 7.5'/><path d='M5 9.5V21h14V9.5'/></svg>");
        }

        .sidebar-link--trophy .sidebar-icon {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230369a1' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M8 21h8'/><path d='M12 17v4'/><path d='M7 4h10l2 5-3 4H8L5 9z'/></svg>");
        }

        .sidebar-link--users .sidebar-icon {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230369a1' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'/><circle cx='9' cy='7' r='4'/><path d='M23 21v-2a4 4 0 0 0-3-3.87'/><path d='M16 3.13a4 4 0 0 1 0 7.75'/></svg>");
        }

        .sidebar-link--settings .sidebar-icon {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230369a1' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='3'/><path d='M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.2a1.7 1.7 0 0 0-1.5 1z'/></svg>");
        }

        .sidebar-link.active.sidebar-link--home .sidebar-icon {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230A1225' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M3 10.5L12 3l9 7.5'/><path d='M5 9.5V21h14V9.5'/></svg>");
        }

        .sidebar-link.active.sidebar-link--trophy .sidebar-icon {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230A1225' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M8 21h8'/><path d='M12 17v4'/><path d='M7 4h10l2 5-3 4H8L5 9z'/></svg>");
        }

        .sidebar-link.active.sidebar-link--users .sidebar-icon {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230A1225' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2'/><circle cx='9' cy='7' r='4'/><path d='M23 21v-2a4 4 0 0 0-3-3.87'/><path d='M16 3.13a4 4 0 0 1 0 7.75'/></svg>");
        }

        .sidebar-link.active.sidebar-link--settings .sidebar-icon {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230A1225' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='3'/><path d='M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.2a1.7 1.7 0 0 0-1.5 1z'/></svg>");
        }

        [data-testid="stSidebar"] .stButton,
        [data-testid="stSidebar"] .stButton > div {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
        }

        [data-testid="stSidebar"] .stButton {
            margin-bottom: 14px;
        }

        [data-testid="stSidebar"] .stButton:last-of-type {
            margin-bottom: 0;
        }

        [data-testid="stSidebar"] .stButton > button {
            font-family: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            width: auto;
            text-align: left;
            padding: 0 12px 0 46px;
            border-radius: 0 !important;
            background: transparent !important;
            background-color: transparent !important;
            border: none !important;
            box-shadow: none !important;
            color: #76869A;
            font-weight: 700;
            letter-spacing: 2.4px;
            text-transform: uppercase;
            transition: color 160ms ease, transform 160ms ease;
            position: relative;
            overflow: visible;
            height: 44px;
            display: flex;
            align-items: center;
            font-size: 13px;
        }

        [data-testid="stSidebar"] .stButton > button:hover:not(:disabled) {
            color: #E0E6EF;
            background: transparent !important;
            transform: translateY(-1px);
        }

        [data-testid="stSidebar"] .stButton > button:active:not(:disabled) {
            transform: translateY(0);
        }

        [data-testid="stSidebar"] .stButton > button:focus-visible {
            outline: 2px solid rgba(100, 176, 255, 0.9);
            outline-offset: 3px;
        }

        [data-testid="stSidebar"] .stButton > button:disabled {
            background: transparent !important;
            border-color: transparent !important;
            color: #E0E6EF;
            opacity: 1;
            cursor: default;
            box-shadow: none !important;
            font-weight: 800;
        }

        [data-testid="stSidebar"] .stButton > button::before {
            content: "";
            position: absolute;
            left: 0;
            top: 50%;
            width: 22px;
            height: 22px;
            transform: translateY(-50%);
            background-repeat: no-repeat;
            background-size: 22px 22px;
            opacity: 1;
            pointer-events: none;
        }

        [data-testid="stSidebar"] .stButton > button::after {
            content: none;
        }

        [data-testid="stSidebar"] .stButton:nth-of-type(1) button::before {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%2354A7FE' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M3 10.5L12 3l9 7.5'/><path d='M5 9.5V21h14V9.5'/></svg>");
        }

        [data-testid="stSidebar"] .stButton:nth-of-type(2) button::before {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%2354A7FE' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M8 21h8'/><path d='M12 17v4'/><path d='M7 4h10l2 5-3 4H8L5 9z'/></svg>");
        }

        [data-testid="stSidebar"] .stButton:nth-of-type(3) button::before {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%2354A7FE' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='9' cy='9' r='4'/><path d='M17 8v6'/><path d='M14 11h6'/><path d='M5 21v-2a4 4 0 0 1 4-4h5'/></svg>");
        }

        [data-testid="stSidebar"] .stButton:nth-of-type(4) button::before {
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' viewBox='0 0 24 24' fill='none' stroke='%2354A7FE' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='3'/><path d='M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 0 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.2a1.7 1.7 0 0 0-1.5 1z'/></svg>");
        }

        [data-testid="stSidebar"] .stButton > button:disabled::before {
            filter: none;
        }

        h1, h2, h3, h4, h5, h6 {
            color: var(--text-primary);
            font-weight: 700;
            letter-spacing: 0.2px;
        }

        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 0.02em;
            color: var(--text-primary);
            font-style: italic;
            font-weight: 800;
            text-shadow: 0 10px 24px rgba(0, 0, 0, 0.45);
        }

        .stMarkdown, .stText, .stTextInput label, .stSelectbox label, .stNumberInput label {
            color: var(--text-secondary);
        }

        .stCaption {
            color: var(--text-secondary);
            opacity: 0.75;
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
            color: var(--chalk);
        }

        [data-baseweb="tab-highlight"] {
            background-color: rgba(245, 245, 245, 0.5);
            height: 3px;
        }

        .stButton > button, .stDownloadButton > button {
            background-color: rgba(10, 16, 26, 0.65);
            color: #e4eeff;
            border: 1px solid rgba(255, 255, 255, 0.14);
            border-radius: 999px;
            padding: 0.45rem 1rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            text-shadow: 0 1px 0 rgba(0, 0, 0, 0.35);
            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            background-color: rgba(92, 167, 255, 0.18);
            border-color: rgba(92, 167, 255, 0.35);
            color: #f3f7ff;
        }

        .stButton > button:active,
        .stDownloadButton > button:active {
            transform: translateY(1px);
            box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.35);
        }

        .top-nav .stButton > button {
            background: transparent;
            border: none;
            color: #9fb0c7;
            letter-spacing: 0.22em;
            text-transform: uppercase;
            font-size: 0.6rem;
            padding: 0.35rem 0.2rem;
            box-shadow: none;
        }

        .top-nav .stButton > button:hover {
            color: #e5efff;
            background: transparent;
        }

        .top-nav .stButton > button:disabled {
            background: transparent;
            color: #f3f7ff;
            box-shadow: inset 0 -2px 0 rgba(92, 167, 255, 0.9);
            opacity: 1;
        }

        .sidebar-nav .stButton > button {
            font-family: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        .stButton > button:active,
        .stDownloadButton > button:active {
            transform: translateY(1px);
            box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.4);
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
            background: linear-gradient(180deg, rgba(14, 21, 35, 0.92) 0%, rgba(10, 16, 26, 0.92) 100%) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            border-radius: 18px;
            box-shadow: 0 14px 32px rgba(0, 0, 0, 0.45);
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
            background-image: radial-gradient(circle at 80% 0%, rgba(92, 167, 255, 0.08), transparent 60%);
            opacity: 0.8;
            pointer-events: none;
        }

        .home-shell h1 {
            position: relative;
            display: inline-block;
            padding-right: 5.5rem;
        }

        .home-shell h1::before {
            content: "";
            position: absolute;
            top: -10px;
            right: -12px;
            width: 70px;
            height: 22px;
            background: linear-gradient(90deg, rgba(203, 180, 125, 0.2), rgba(203, 180, 125, 0.12));
            border: 1px solid rgba(245, 245, 245, 0.1);
            border-radius: 6px;
            transform: rotate(-6deg);
            filter: blur(0.2px);
            opacity: 0.8;
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

        .pos-qb,
        .pos-rb,
        .pos-wr,
        .pos-te,
        .pos-k {
            background: rgba(245, 245, 245, 0.08);
            color: rgba(245, 245, 245, 0.85);
        }

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
            border-color: rgba(245, 245, 245, 0.3);
            box-shadow: 0 0 0 2px rgba(245, 245, 245, 0.12);
        }

        .draft-pick.user-pick {
            background: rgba(203, 180, 125, 0.18);
            border-color: rgba(203, 180, 125, 0.3);
        }

        .player-row {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer;
            position: relative;
        }

        .player-row:hover {
            transform: translateY(-2px) scale(1.01);
            background: rgba(245, 245, 245, 0.06);
            box-shadow: 0 8px 22px rgba(0, 0, 0, 0.35), inset 0 0 0 1px rgba(245, 245, 245, 0.12);
            border-radius: 12px;
            z-index: 10;
        }

        .player-name {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }

        .player-row:hover .player-name {
            color: var(--chalk);
            font-weight: 700;
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
            background: rgba(245, 245, 245, 0.08);
            border-color: rgba(245, 245, 245, 0.24);
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
            letter-spacing: 0.12em;
            color: var(--chalk);
            font-weight: 700;
            text-shadow: 0 1px 0 rgba(0, 0, 0, 0.35);
        }

        .section-header__meta {
            font-size: 0.7rem;
            color: var(--text-secondary);
        }

        .dashboard-card__header,
        .player-card-title,
        .settings-title,
        .myteam-title,
        .trade-title,
        .waiver-title,
        .draft-title,
        .public-title,
        .section-header__title {
            position: relative;
            color: #7fb3ff !important;
            letter-spacing: 0.18em;
            text-transform: uppercase;
        }

        .dashboard-card__header::after,
        .player-card-title::after,
        .settings-title::after,
        .myteam-title::after,
        .trade-title::after,
        .waiver-title::after,
        .draft-title::after,
        .public-title::after,
        .section-header__title::after {
            content: none;
        }

        .stat-pill {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 999px;
            background: rgba(10, 16, 26, 0.7);
            border: 1px solid rgba(92, 167, 255, 0.35);
            font-size: 0.65rem;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            color: #7fb3ff;
            font-weight: 700;
            text-shadow: 0 1px 0 rgba(0, 0, 0, 0.35);
        }

        .stat-pill.primary {
            background: rgba(92, 167, 255, 0.18);
            border-color: rgba(92, 167, 255, 0.45);
            color: #e8f1ff;
        }

        .stat-pill.accent {
            background: rgba(220, 80, 80, 0.16);
            border-color: rgba(220, 80, 80, 0.3);
            color: #f3f7ff;
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
            position: relative;
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

        .mini-row,
        .rank-row,
        .watch-row,
        .game-row {
            position: relative;
        }

        :is(.mini-row, .rank-row, .watch-row, .game-row, .data-table__row):hover {
            background: rgba(245, 245, 245, 0.04);
        }

        :is(.mini-row, .rank-row, .watch-row, .game-row, .data-table__row):hover::before {
            content: none;
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
