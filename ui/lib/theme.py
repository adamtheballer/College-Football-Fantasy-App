import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg-main: #0b0b0b;
            --bg-surface: #1a1a1a;
            --bg-surface-2: #242424;
            --text-primary: #ededed;
            --text-secondary: #9a9a9a;
            --accent-green: #2ed158;
            --accent-blue: #4aa3ff;
            --status-danger: #ff5b5b;
        }

        html, body, [data-testid="stAppViewContainer"] {
            background: radial-gradient(1200px 600px at 80% -10%, #1b1b1b 0%, var(--bg-main) 60%);
            color: var(--text-primary);
        }

        [data-testid="stSidebar"] {
            background-color: #141414;
            border-right: 1px solid #202020;
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
            border: 1px solid #2a2a2a;
            border-radius: 12px;
            color: var(--text-primary);
        }

        textarea, input, select {
            color: var(--text-primary);
        }

        [data-baseweb="tab-list"] {
            border-bottom: 1px solid #1f1f1f;
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
            background-color: transparent;
            color: var(--accent-blue);
            border: 1px solid var(--accent-blue);
            border-radius: 999px;
            padding: 0.35rem 0.9rem;
            font-weight: 600;
        }

        .stButton > button:hover {
            border-color: #7bb9ff;
            color: #cfe6ff;
        }

        [data-testid="stForm"] {
            background: var(--bg-surface);
            border: 1px solid #232323;
            border-radius: 16px;
            padding: 1rem 1.2rem;
        }

        .stDataFrame {
            background: var(--bg-surface);
            border: 1px solid #232323;
            border-radius: 16px;
        }

        .stAlert {
            border-radius: 12px;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )
