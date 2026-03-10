import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.rotowire import RotowireClient
from collegefootballfantasy_api.app.models import league, roster, team, user  # noqa: F401
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.services.power4 import conference_for_school, resolve_power4_school


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _clean_text(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split())
    return cleaned or None


def _map_status(status: str) -> str:
    status = status.upper()
    if any(
        token in status
        for token in (
            "OUT FOR SEASON",
            "SEASON-ENDING",
            "SEASON ENDING",
            "LOST FOR THE SEASON",
            "REMAINDER OF THE SEASON",
            "MISS THE SEASON",
        )
    ):
        return "OUT_FOR_SEASON"
    if "OUT" in status:
        return "OUT"
    if "DOUBTFUL" in status:
        return "DOUBTFUL"
    if "QUESTION" in status:
        return "QUESTIONABLE"
    if "PROBABLE" in status:
        return "PROBABLE"
    return "FULL"


def _injury_changed(
    existing: Injury,
    *,
    status: str,
    injury_desc: str | None,
    return_timeline: str | None,
    practice_level: str | None,
    notes: str | None,
    is_game_time_decision: bool,
) -> bool:
    return any(
        (
            existing.status != status,
            _clean_text(existing.injury) != _clean_text(injury_desc),
            _clean_text(existing.return_timeline) != _clean_text(return_timeline),
            _clean_text(existing.practice_level) != _clean_text(practice_level),
            _clean_text(existing.notes) != _clean_text(notes),
            bool(existing.is_game_time_decision) != bool(is_game_time_decision),
        )
    )


def _create_injury_alert(
    *,
    player: Player,
    team_name: str,
    conference: str | None,
    status: str,
    season: int,
    week: int,
    title: str,
    body: str,
) -> NotificationLog:
    return NotificationLog(
        user_key=None,
        alert_type="INJURY",
        title=title,
        body=body,
        payload={
            "player_id": player.id,
            "team": team_name,
            "conference": conference,
            "status": status,
            "season": season,
            "week": week,
        },
    )


def ingest_once(season: int, week: int, emit_alerts: bool = True) -> tuple[int, int, int, int]:
    """Ingest one injury snapshot and emit alerts for new/changed entries.

    Returns (created_count, updated_count, removed_count, emitted_alert_count).
    """
    client = RotowireClient()
    rows = client.get_injuries()

    session = SessionLocal()
    try:
        players = session.scalars(select(Player)).all()
        player_index: dict[tuple[str, str], Player] = {}
        for player in players:
            canonical_team = resolve_power4_school(player.school or "")
            player_index[(_normalize(player.name), _normalize(canonical_team or player.school))] = player

        existing_rows = session.scalars(
            select(Injury).where(Injury.season == season, Injury.week == week)
        ).all()
        existing_by_player_id: dict[int, Injury] = {}
        duplicate_rows: list[Injury] = []
        for row in existing_rows:
            if row.player_id in existing_by_player_id:
                duplicate_rows.append(row)
            else:
                existing_by_player_id[row.player_id] = row
        for dup in duplicate_rows:
            session.delete(dup)

        created = 0
        updated = 0
        removed = 0
        emitted_alerts = 0
        seen_player_ids: set[int] = set()

        for row in rows:
            name = row.get("Player") or row.get("Name") or row.get("Player Name") or row.get("player")
            team_name = row.get("Team") or row.get("School") or row.get("team")
            raw_status = row.get("Status") or row.get("Game Status") or ""
            position = row.get("Position") or row.get("Pos") or row.get("position") or "UNK"
            injury_desc = _clean_text(row.get("Injury") or row.get("injury") or None)
            notes = _clean_text(row.get("Notes") or row.get("notes") or injury_desc)
            return_timeline = _clean_text(
                row.get("Expected Return")
                or row.get("Return")
                or row.get("Return Timeline")
                or row.get("Timeline")
                or None
            )
            practice_level = _clean_text(
                row.get("Practice")
                or row.get("Practice Participation")
                or row.get("Practice Status")
                or None
            )

            if not name or not team_name:
                continue

            canonical_team = resolve_power4_school(team_name)
            if not canonical_team:
                continue

            key = (_normalize(name), _normalize(canonical_team))
            player = player_index.get(key)
            if not player:
                player = Player(
                    name=name.strip(),
                    school=canonical_team,
                    position=position.strip().upper(),
                )
                session.add(player)
                session.flush()
                player_index[key] = player

            seen_player_ids.add(player.id)
            mapped_status = _map_status(raw_status)
            is_gtd = "GTD" in raw_status.upper() or "GAME-TIME DECISION" in raw_status.upper()
            team_conference = conference_for_school(canonical_team)
            existing = existing_by_player_id.get(player.id)

            if existing:
                changed = _injury_changed(
                    existing,
                    status=mapped_status,
                    injury_desc=injury_desc,
                    return_timeline=return_timeline,
                    practice_level=practice_level,
                    notes=notes,
                    is_game_time_decision=is_gtd,
                )
                previous_status = existing.status
                existing.status = mapped_status
                existing.injury = injury_desc
                existing.return_timeline = return_timeline
                existing.practice_level = practice_level
                existing.is_game_time_decision = is_gtd
                existing.notes = notes
                session.add(existing)
                if changed:
                    updated += 1
                    if emit_alerts:
                        session.add(
                            _create_injury_alert(
                                player=player,
                                team_name=canonical_team,
                                conference=team_conference,
                                status=mapped_status,
                                season=season,
                                week=week,
                                title=f"Injury Update: {player.name}",
                                body=(
                                    f"{player.name} ({canonical_team} {player.position}) "
                                    f"changed from {previous_status} to {mapped_status}."
                                ),
                            )
                        )
                        emitted_alerts += 1
                continue

            session.add(
                Injury(
                    player_id=player.id,
                    season=season,
                    week=week,
                    status=mapped_status,
                    injury=injury_desc,
                    return_timeline=return_timeline,
                    practice_level=practice_level,
                    is_game_time_decision=is_gtd,
                    is_returning=False,
                    notes=notes,
                )
            )
            created += 1
            if emit_alerts:
                session.add(
                    _create_injury_alert(
                        player=player,
                        team_name=canonical_team,
                        conference=team_conference,
                        status=mapped_status,
                        season=season,
                        week=week,
                        title=f"New Injury: {player.name}",
                        body=f"{player.name} ({canonical_team} {player.position}) is now listed as {mapped_status}.",
                    )
                )
                emitted_alerts += 1

        for player_id, existing in existing_by_player_id.items():
            if player_id in seen_player_ids:
                continue
            session.delete(existing)
            removed += 1

        session.commit()
        return created, updated, removed, emitted_alerts
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest CFB injury report from Rotowire.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument(
        "--emit-alerts",
        dest="emit_alerts",
        action="store_true",
        default=True,
        help="Emit INJURY notifications for new/changed rows (default: enabled).",
    )
    parser.add_argument(
        "--no-emit-alerts",
        dest="emit_alerts",
        action="store_false",
        help="Do not emit INJURY notifications.",
    )
    args = parser.parse_args()

    created, updated, removed, alerts = ingest_once(args.season, args.week, emit_alerts=args.emit_alerts)
    print(
        f"Ingested injuries for season={args.season}, week={args.week}: "
        f"created={created}, updated={updated}, removed={removed}, alerts={alerts}"
    )


if __name__ == "__main__":
    main()
