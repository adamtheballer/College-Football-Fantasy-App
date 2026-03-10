from __future__ import annotations

import streamlit as st

from ui.lib.team_branding import team_logo_html


def render_league_row(league: dict, on_jump, index: int = 0) -> None:
    trophy_svg = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M7 4h10v3a5 5 0 0 1-4 5v2h3v3H8v-3h3v-2a5 5 0 0 1-4-5V4z"/>'
        '<path d="M5 6H3v2a4 4 0 0 0 4 4"/><path d="M19 6h2v2a4 4 0 0 1-4 4"/>'
        "</svg>"
    )
    star_svg = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>'
        "</svg>"
    )
    target_svg = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>'
        "</svg>"
    )
    user_svg = (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M18 20a6 6 0 0 0-12 0"/><circle cx="12" cy="10" r="4"/>'
        "</svg>"
    )
    icon_variants = [
        (trophy_svg, "league-card__icon--blue", "league-card__glow--blue"),
        (star_svg, "league-card__icon--orange", "league-card__glow--orange"),
        (target_svg, "league-card__icon--emerald", "league-card__glow--emerald"),
    ]
    icon_svg, icon_class, glow_class = icon_variants[index % len(icon_variants)]
    member_count = league.get("team_count", 0)
    avatar_count = min(4, member_count)
    extra_members = max(0, member_count - avatar_count)
    avatars = "".join(f'<span class="league-card__avatar">{user_svg}</span>' for _ in range(avatar_count))
    left_html = (
        '<div class="league-card__panel league-card__panel--left">'
        '<div class="league-card__left">'
        f'<div class="league-card__glow {glow_class}"></div>'
        f'<div class="league-card__icon {icon_class}">{icon_svg}</div>'
        f'<div class="league-card__name">{league["name"]}</div>'
        f'<div class="league-card__meta">Week {league["current_week"]} &bull; {league["team_count"]} Teams</div>'
        '<div class="league-card__members">'
        f'<div class="league-card__avatars">{avatars}</div>'
        f'<span class="league-card__members-text">+ {extra_members} Members</span>'
        "</div>"
        "</div></div>"
    )

    preview_lines = []
    for entry in league.get("standings_preview", []):
        preview_lines.append(
            '<div class="league-standings-row">'
            f'<div class="league-standings-rank">{entry["rank"]}.</div>'
            '<div class="league-standings-team">'
            f'{team_logo_html(entry["team"], 24)}'
            f'<span class="league-standings-name">{entry["team"]}</span>'
            f'<span class="league-standings-record">({entry["record"]})</span>'
            "</div></div>"
        )
    preview_html = "".join(preview_lines) if preview_lines else '<div class="league-standings-empty">No standings available.</div>'

    st.markdown('<div class="league-card">', unsafe_allow_html=True)
    left_col, mid_col, right_col = st.columns([1.1, 1.6, 1])
    with left_col:
        st.markdown(left_html, unsafe_allow_html=True)
    with mid_col:
        st.markdown(
            '<div class="league-card__panel league-card__panel--mid">'
            '<div class="league-standings">'
            '<div class="league-standings-title">Standings Preview</div>'
            f"{preview_html}</div></div>",
            unsafe_allow_html=True,
        )
    with right_col:
        st.markdown('<div class="league-card__panel league-card__panel--right league-card__cta">', unsafe_allow_html=True)
        if st.button("Jump to League", key=f"jump_{league['id']}"):
            on_jump(league["id"])
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
