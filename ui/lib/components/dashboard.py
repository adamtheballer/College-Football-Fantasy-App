from __future__ import annotations

import html

from ui.lib.team_branding import team_logo_html


def _escape(value: object) -> str:
    return html.escape(str(value))


def skeleton_rows(count: int = 3) -> str:
    lines = []
    for index in range(count):
        width = 85 - (index * 10)
        lines.append(f'<div class="skeleton-line" style="width: {width}%"></div>')
    return "".join(lines)


def empty_state(message: str) -> str:
    return f'<div class="empty-state">{_escape(message)}</div>'


def dashboard_card(title: str, body_html: str, footer_html: str | None = None) -> str:
    footer = f'<div class="dashboard-card__footer">{footer_html}</div>' if footer_html else ""
    return (
        f'<div class="dashboard-card">'
        f'<div class="dashboard-card__header">{_escape(title)}</div>'
        f'<div class="dashboard-card__body">{body_html}</div>'
        f"{footer}</div>"
    )


def team_mini_card(team: dict) -> str:
    return (
        '<div class="mini-row">'
        '<div class="mini-row__main">'
        f'<div class="mini-title">{team_logo_html(team["team"], 22)} {_escape(team["team"])}</div>'
        f'<div class="mini-sub">{_escape(team["league"])}</div>'
        '</div>'
        '<div class="mini-row__meta">'
        f'<div class="mini-stat">{_escape(team["record"])}</div>'
        f'<div class="mini-sub">{_escape(team["points"])} pts</div>'
        f'<div class="mini-sub">Next: {_escape(team["next_opponent"])}</div>'
        f'<div class="mini-sub">{_escape(team["kickoff"])}</div>'
        "</div>"
        "</div>"
    )


def matchup_mini_card(matchup: dict) -> str:
    return (
        '<div class="mini-row">'
        '<div class="mini-row__main">'
        f'<div class="mini-title">{team_logo_html(matchup["away"], 20)} {_escape(matchup["away"])}</div>'
        f'<div class="mini-sub">{team_logo_html(matchup["home"], 18)} {_escape(matchup["home"])}</div>'
        "</div>"
        '<div class="mini-row__meta">'
        f'<div class="mini-score">{_escape(matchup["away_score"])} - {_escape(matchup["home_score"])}</div>'
        f'<div class="mini-sub">{_escape(matchup["status"])}</div>'
        f'<div class="mini-sub">{_escape(matchup["week"])}</div>'
        "</div>"
        "</div>"
    )


def power_rankings_table(rankings: list[dict]) -> str:
    if not rankings:
        return empty_state("No rankings available.")
    rows = []
    for entry in rankings:
        trend_value = str(entry.get("trend", "0"))
        trend_class = "trend-neutral"
        if trend_value.startswith("+"):
            trend_class = "trend-up"
        elif trend_value.startswith("-"):
            trend_class = "trend-down"
        rows.append(
            '<div class="rank-row">'
            f'<div class="rank-cell rank">{_escape(entry["rank"])}</div>'
            f'<div class="rank-cell team">{_escape(entry["team"])}</div>'
            f'<div class="rank-cell record">{_escape(entry["record"])}</div>'
            f'<div class="rank-cell {trend_class}">{_escape(trend_value)}</div>'
            "</div>"
        )
    header = (
        '<div class="rank-row rank-header">'
        '<div class="rank-cell rank">#</div>'
        '<div class="rank-cell team">Team</div>'
        '<div class="rank-cell record">W-L</div>'
        '<div class="rank-cell">Trend</div>'
        "</div>"
    )
    return f'<div class="rank-table">{header}{"".join(rows)}</div>'


def news_list(items: list[dict]) -> str:
    if not items:
        return empty_state("No news yet.")
    rows = []
    for item in items:
        rows.append(
            '<div class="news-item">'
            f'<div class="news-title">{_escape(item["title"])}</div>'
            f'<div class="news-summary">{_escape(item["summary"])}</div>'
            f'<div class="news-meta">{_escape(item["source"])} · {_escape(item["time"])}</div>'
            "</div>"
        )
    return f'<div class="news-list">{"".join(rows)}</div>'
