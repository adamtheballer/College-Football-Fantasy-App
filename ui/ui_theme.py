from __future__ import annotations

import html

import streamlit as st

from ui.lib.theme import apply_theme as _apply_theme


def apply_theme() -> None:
    _apply_theme()


def section_label(text: str) -> str:
    safe_text = html.escape(text)
    return f'<div class="section-header__title">{safe_text}</div>'


def stamp(text: str) -> str:
    safe_text = html.escape(text)
    return f'<span class="stat-pill">{safe_text}</span>'


def panel(title: str, content_fn) -> None:
    safe_title = html.escape(title)
    st.markdown(
        f'<div class="dashboard-card"><div class="dashboard-card__header">{safe_title}</div><div class="dashboard-card__body">',
        unsafe_allow_html=True,
    )
    content_fn()
    st.markdown("</div></div>", unsafe_allow_html=True)
