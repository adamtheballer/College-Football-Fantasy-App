import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg-main: #000000;
            --bg-surface: #1a1a1a;
            --bg-surface-2: #2a2a2a;
            --text-primary: #f5f5f5;
            --text-secondary: #b0b0b0;
            --accent-green: #4caf50;
            --accent-blue: #007bff;
            --accent-muted: #333333;
            --status-danger: #ff5b5b;
            --border-subtle: #333333;
            --border-strong: #444444;
            --radius-lg: 12px;
            --radius-xl: 16px;
        }

        html, body, [data-testid="stAppViewContainer"] {
            background: linear-gradient(180deg, #000000 0%, #1a1a1a 100%);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #000000 0%, #1a1a1a 100%);
            border-right: 1px solid var(--border-subtle);
        }

        h1, h2, h3, h4, h5, h6 {
            color: var(--text-primary);
            font-weight: 700;
            letter-spacing: 0.2px;
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
            background-color: #333333;
            color: #ffffff;
            border: 1px solid #555555;
            border-radius: 999px;
            padding: 0.45rem 1rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stButton > button:hover {
            background-color: #444444;
            border-color: #666666;
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

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }

        </style>
        """,
        unsafe_allow_html=True,
    )
