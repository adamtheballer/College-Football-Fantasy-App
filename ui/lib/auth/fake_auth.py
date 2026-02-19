from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

SESSION_PATH = Path(__file__).resolve().parents[2] / ".session.json"


def _load_session_from_disk() -> dict | None:
    if not SESSION_PATH.exists():
        return None
    try:
        with SESSION_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _save_session_to_disk(session: dict | None) -> None:
    if session is None:
        if SESSION_PATH.exists():
            SESSION_PATH.unlink()
        return
    SESSION_PATH.write_text(json.dumps(session, indent=2), encoding="utf-8")


def use_session() -> dict | None:
    if "auth_session" not in st.session_state:
        st.session_state["auth_session"] = _load_session_from_disk()
    return st.session_state.get("auth_session")


def login(email: str, remember: bool = True) -> dict:
    name_part = email.split("@")[0] if "@" in email else email
    display_name = name_part.replace(".", " ").title() or "User"
    session = {
        "name": display_name,
        "email": email,
        "avatar": display_name[:2].upper(),
    }
    st.session_state["auth_session"] = session
    if remember:
        _save_session_to_disk(session)
    return session


def logout() -> None:
    st.session_state["auth_session"] = None
    _save_session_to_disk(None)
