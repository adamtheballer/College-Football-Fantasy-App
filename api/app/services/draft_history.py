from collections import defaultdict
from html import escape

from sqlalchemy.orm import Session

from api.app.models.draft import Draft
from api.app.models.draft_pick import DraftPick
from api.app.models.league import League
from api.app.models.player import Player
from api.app.models.roster import RosterEntry
from api.app.models.team import Team
from api.app.schemas.draft_room import DraftHistoryResponse


def generate_draft_history(db: Session, *, league: League, draft_row: Draft) -> DraftHistoryResponse:
    pick_rows = (
        db.query(DraftPick, Team, Player)
        .join(Team, Team.id == DraftPick.team_id)
        .join(Player, Player.id == DraftPick.player_id)
        .filter(DraftPick.draft_id == draft_row.id)
        .order_by(DraftPick.overall_pick.asc())
        .all()
    )
    roster_rows = (
        db.query(RosterEntry, Team, Player)
        .join(Team, Team.id == RosterEntry.team_id)
        .join(Player, Player.id == RosterEntry.player_id)
        .filter(RosterEntry.league_id == league.id)
        .order_by(Team.name.asc(), RosterEntry.slot.asc(), RosterEntry.created_at.asc())
        .all()
    )

    rounds_by_number: dict[int, list[dict]] = defaultdict(list)
    plain_lines = [f"{league.name} Draft History", ""]
    for pick, team, player in pick_rows:
        row = {
            "overall_pick": pick.overall_pick,
            "round_number": pick.round_number,
            "round_pick": pick.round_pick,
            "team_id": team.id,
            "team_name": team.name,
            "player_id": player.id,
            "player_name": player.name,
            "player_position": player.position,
            "player_school": player.school,
        }
        rounds_by_number[pick.round_number].append(row)

    rounds = [
        {"round_number": round_number, "picks": rounds_by_number[round_number]}
        for round_number in sorted(rounds_by_number)
    ]
    for round_payload in rounds:
        plain_lines.append(f"Round {round_payload['round_number']}")
        for pick in round_payload["picks"]:
            plain_lines.append(
                f"{pick['round_number']}.{pick['round_pick']} "
                f"{pick['team_name']}: {pick['player_name']} "
                f"({pick['player_position']}, {pick['player_school']})"
            )
        plain_lines.append("")

    roster_by_team: dict[int, dict] = {}
    for roster_entry, team, player in roster_rows:
        team_payload = roster_by_team.setdefault(
            team.id,
            {"team_id": team.id, "team_name": team.name, "players": []},
        )
        team_payload["players"].append(
            {
                "slot": roster_entry.slot,
                "player_id": player.id,
                "player_name": player.name,
                "player_position": player.position,
                "player_school": player.school,
            }
        )
    rosters = sorted(roster_by_team.values(), key=lambda row: row["team_name"])

    plain_lines.append("Rosters")
    for roster in rosters:
        plain_lines.append(roster["team_name"])
        for player in roster["players"]:
            plain_lines.append(
                f"- {player['slot']}: {player['player_name']} "
                f"({player['player_position']}, {player['player_school']})"
            )
        plain_lines.append("")

    html_parts = [f"<h1>{escape(league.name)} Draft History</h1>"]
    for round_payload in rounds:
        html_parts.append(f"<h2>Round {round_payload['round_number']}</h2><ol>")
        for pick in round_payload["picks"]:
            html_parts.append(
                "<li>"
                f"<strong>{pick['round_number']}.{pick['round_pick']}</strong> "
                f"{escape(pick['team_name'])}: {escape(pick['player_name'])} "
                f"({escape(pick['player_position'])}, {escape(pick['player_school'])})"
                "</li>"
            )
        html_parts.append("</ol>")
    html_parts.append("<h2>Rosters</h2>")
    for roster in rosters:
        html_parts.append(f"<h3>{escape(roster['team_name'])}</h3><ul>")
        for player in roster["players"]:
            html_parts.append(
                "<li>"
                f"<strong>{escape(player['slot'])}</strong>: {escape(player['player_name'])} "
                f"({escape(player['player_position'])}, {escape(player['player_school'])})"
                "</li>"
            )
        html_parts.append("</ul>")

    return DraftHistoryResponse(
        league_id=league.id,
        draft_id=draft_row.id,
        pick_count=len(pick_rows),
        plain_text="\n".join(plain_lines).strip(),
        html="".join(html_parts),
        rounds=rounds,
        rosters=rosters,
    )
