from __future__ import annotations

import hashlib


_PALETTE = [
    "#4aa3ff",
    "#42d17c",
    "#f0b84c",
    "#ff6b6b",
    "#a86bff",
    "#2ed158",
    "#ff8f3f",
    "#3ccfcf",
]


def team_color(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    index = int(digest[:2], 16) % len(_PALETTE)
    return _PALETTE[index]


def team_initials(name: str) -> str:
    parts = name.split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    return name[:2].upper()


def team_logo_html(name: str, size: int = 26) -> str:
    color = team_color(name)
    initials = team_initials(name)
    return (
        f'<span class="team-logo" style="background:{color}; width:{size}px; height:{size}px;">'
        f"{initials}</span>"
    )
