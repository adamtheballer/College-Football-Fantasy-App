from __future__ import annotations

import html


def section_header(title: str, meta: str | None = None) -> str:
    meta_html = f'<div class="section-header__meta">{html.escape(meta)}</div>' if meta else ""
    return (
        f'<div class="section-header">'
        f'<div class="section-header__title">{html.escape(title)}</div>'
        f"{meta_html}</div>"
    )


def stat_pill(label: str, variant: str = "default") -> str:
    return f'<span class="stat-pill {variant}">{html.escape(label)}</span>'


def team_logo(label: str) -> str:
    initials = "".join(part[0] for part in label.split()[:2]).upper() or label[:2].upper()
    return f'<span class="team-logo">{html.escape(initials)}</span>'
