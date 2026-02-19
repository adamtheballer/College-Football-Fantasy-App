from __future__ import annotations

import html

from ui.lib.team_branding import team_logo_html


def _escape(value: object) -> str:
    return html.escape(str(value))


def matchup_summary_html(matchup: dict) -> str:
    away = matchup["away"]
    home = matchup["home"]
    away_lineup = away["lineup"]
    home_lineup = home["lineup"]
    away_prob = int(matchup["win_prob"]["away"] * 100)
    home_prob = int(matchup["win_prob"]["home"] * 100)

    return f"""
    <div class="matchup-summary">
        <div class="matchup-team">
            <div class="matchup-name">{team_logo_html(away["name"])} {_escape(away["name"])}</div>
            <div class="matchup-record">{_escape(away["record"])}</div>
            <div class="matchup-score">{away_lineup["total_points"]}</div>
            <div class="matchup-proj">Proj {away_lineup["total_proj"]}</div>
        </div>
        <div class="matchup-center">
            <div class="matchup-status">{_escape(matchup["status"])} · Week {matchup["week"]}</div>
            <div class="win-prob">
                <div class="win-prob__bar">
                    <div class="win-prob__away" style="width: {away_prob}%"></div>
                    <div class="win-prob__home" style="width: {home_prob}%"></div>
                </div>
                <div class="win-prob__labels">
                    <span>{away_prob}%</span>
                    <span>{home_prob}%</span>
                </div>
                <div class="win-prob__caption">Win Probability</div>
            </div>
        </div>
        <div class="matchup-team">
            <div class="matchup-name">{team_logo_html(home["name"])} {_escape(home["name"])}</div>
            <div class="matchup-record">{_escape(home["record"])}</div>
            <div class="matchup-score">{home_lineup["total_points"]}</div>
            <div class="matchup-proj">Proj {home_lineup["total_proj"]}</div>
        </div>
    </div>
    """


def lineup_table_html(title: str, rows: list[dict]) -> str:
    header = """
        <div class="lineup-row lineup-header">
            <div>Player</div>
            <div>Pos</div>
            <div>Pts</div>
            <div>Proj</div>
            <div>Status</div>
            <div>Key Stats</div>
        </div>
    """
    row_html = []
    for player in rows:
        breakdown = player.get("stat_breakdown", {})
        breakdown_text = " · ".join(f"{key} {value}" for key, value in breakdown.items())
        stats_text = f"{player['stats']} · {breakdown_text}" if breakdown_text else player["stats"]
        row_html.append(
            f"""
            <div class="lineup-row">
                <div class="lineup-player">
                    <div class="lineup-name">{_escape(player["name"])}</div>
                    <div class="lineup-sub">{_escape(player["team"])} · {_escape(player["slot"])}</div>
                </div>
                <div>{_escape(player["pos"])}</div>
                <div class="lineup-stat">{player["points"]}</div>
                <div class="lineup-stat">{player["proj"]}</div>
                <div class="lineup-status">{_escape(player["status"])}</div>
                <div class="lineup-stats">{_escape(stats_text)}</div>
            </div>
            """
        )
    body = "".join(row_html) if row_html else '<div class="empty-state">No players.</div>'
    return f"""
    <div class="lineup-section">
        <div class="lineup-title">{_escape(title)}</div>
        <div class="lineup-table">{header}{body}</div>
    </div>
    """


def team_lineup_html(team: dict) -> str:
    lineup = team["lineup"]
    starters_html = lineup_table_html("Starters", lineup["starters"])
    bench_html = lineup_table_html("Bench", lineup["bench"])
    return f"""
    <div class="team-lineup">
        <div class="team-lineup__header">
            <div class="team-lineup__name">{_escape(team["name"])}</div>
            <div class="team-lineup__record">{_escape(team["record"])}</div>
        </div>
        {starters_html}
        {bench_html}
    </div>
    """
