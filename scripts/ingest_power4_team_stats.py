import argparse
import os
import re
import sys
from datetime import datetime

from sqlalchemy import select

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.integrations.cfbd import CFBDClient
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.team_stats_snapshot import TeamStatsSnapshot
from collegefootballfantasy_api.app.services.power4 import (
    CANONICAL_POWER4_TEAMS,
    canonical_school_name,
    conference_for_school,
    is_power4_school,
    list_power4_teams,
)


def _normalize_stat_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    value_str = str(value).strip()
    if not value_str:
        return None
    value_str = value_str.replace("%", "")
    try:
        return float(value_str)
    except ValueError:
        return None


def _is_defensive_stat(row: dict, stat_name: str) -> bool:
    for key in ("category", "statType", "unit", "side"):
        value = row.get(key)
        if isinstance(value, str):
            lower = value.lower()
            if "def" in lower:
                return True
            if "off" in lower:
                return False

    stat = stat_name.lower()
    defense_keywords = (
        "allowed",
        "opponent",
        "opp_",
        "defensive",
        "takeaway",
        "interception",
        "havoc",
        "pressure",
        "sacks",
    )
    offense_exclusions = ("sacks_allowed",)
    key = _normalize_stat_key(stat)
    if key in offense_exclusions:
        return False
    return any(keyword in stat for keyword in defense_keywords)


def _ingest_games(client: CFBDClient, season: int, conferences: list[str], max_week: int) -> int:
    session = SessionLocal()
    ingested = 0
    seen_ids: set[str] = set()
    try:
        teams = []
        for conference in conferences:
            teams.extend(list_power4_teams(conference))
        for team_name in sorted(set(teams)):
            rows = client.get_games(season=season, season_type="regular", team=team_name)
            for row in rows:
                external_id = str(
                    row.get("id")
                    or row.get("gameId")
                    or f"{season}-{row.get('week')}-{row.get('homeTeam')}-{row.get('awayTeam')}"
                )
                if external_id in seen_ids:
                    continue
                seen_ids.add(external_id)

                home_raw = row.get("homeTeam") or row.get("home_team") or ""
                away_raw = row.get("awayTeam") or row.get("away_team") or ""
                home_team = canonical_school_name(home_raw) or home_raw
                away_team = canonical_school_name(away_raw) or away_raw
                home_points = row.get("homePoints")
                away_points = row.get("awayPoints")

                if not home_team or not away_team:
                    continue
                if not is_power4_school(home_team) and not is_power4_school(away_team):
                    continue

                existing = session.scalar(select(Game).where(Game.external_id == external_id))
                game = existing or Game(
                    external_id=external_id,
                    season=season,
                    week=int(row.get("week") or 0),
                )
                game.season = season
                game.week = int(row.get("week") or game.week or 0)
                game.season_type = row.get("seasonType") or row.get("season_type") or "regular"
                start_date = row.get("startDate") or row.get("start_date")
                if isinstance(start_date, str):
                    try:
                        start_date = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                    except ValueError:
                        start_date = None
                game.start_date = start_date
                game.home_team = str(home_team)
                game.away_team = str(away_team)
                game.home_points = home_points
                game.away_points = away_points
                game.neutral_site = bool(row.get("neutralSite") or row.get("neutral_site") or False)
                session.add(game)
                ingested += 1
        session.commit()
    finally:
        session.close()
    return ingested


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Power 4 team season offense/defense/advanced stats.")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--conference", type=str, default="ALL", choices=["ALL", "SEC", "BIG10", "BIG12", "ACC"])
    parser.add_argument("--scope", type=str, default="season")
    parser.add_argument("--week", type=int, default=0)
    parser.add_argument("--max-week", type=int, default=16)
    parser.add_argument("--skip-games", action="store_true")
    args = parser.parse_args()

    conferences = (
        [args.conference]
        if args.conference != "ALL"
        else sorted(CANONICAL_POWER4_TEAMS.keys())
    )
    client = CFBDClient()
    accumulator: dict[str, dict[str, object]] = {}

    for conference in conferences:
        for team in list_power4_teams(conference):
            accumulator[team] = {
                "conference": conference,
                "offense": {},
                "defense": {},
                "advanced": {},
            }

        season_rows = client.get_season_stats(season=args.season, conference=conference)
        for row in season_rows:
            team_raw = row.get("team") or row.get("school") or row.get("teamName")
            if not isinstance(team_raw, str):
                continue
            team = canonical_school_name(team_raw)
            if not team:
                continue
            stat_name = (
                row.get("statName")
                or row.get("stat")
                or row.get("name")
                or row.get("category")
            )
            if not isinstance(stat_name, str):
                continue
            value = _as_float(row.get("statValue") or row.get("value"))
            if value is None:
                continue
            key = _normalize_stat_key(stat_name)
            if not key:
                continue
            side = "defense" if _is_defensive_stat(row, stat_name) else "offense"
            team_bucket = accumulator.setdefault(
                team,
                {"conference": conference_for_school(team) or conference, "offense": {}, "defense": {}, "advanced": {}},
            )
            stats_dict = team_bucket[side]
            if isinstance(stats_dict, dict):
                stats_dict[key] = round(value, 4)

        advanced_rows = client.get_season_advanced_stats(season=args.season, conference=conference)
        for row in advanced_rows:
            team_raw = row.get("team") or row.get("school") or row.get("teamName")
            if not isinstance(team_raw, str):
                continue
            team = canonical_school_name(team_raw)
            if not team:
                continue
            team_bucket = accumulator.setdefault(
                team,
                {"conference": conference_for_school(team) or conference, "offense": {}, "defense": {}, "advanced": {}},
            )
            advanced_dict = team_bucket["advanced"]
            if not isinstance(advanced_dict, dict):
                continue

            if isinstance(row.get("offense"), dict):
                advanced_dict["offense"] = row["offense"]
            if isinstance(row.get("defense"), dict):
                advanced_dict["defense"] = row["defense"]

            for key, value in row.items():
                if key in {"team", "teamName", "school", "conference", "offense", "defense"}:
                    continue
                if isinstance(value, (int, float, str, bool)):
                    advanced_dict[_normalize_stat_key(str(key))] = value

    session = SessionLocal()
    upserted = 0
    try:
        for team_name, payload in accumulator.items():
            conference = payload["conference"]
            if not isinstance(conference, str):
                continue
            existing = session.scalar(
                select(TeamStatsSnapshot).where(
                    TeamStatsSnapshot.team_name == team_name,
                    TeamStatsSnapshot.season == args.season,
                    TeamStatsSnapshot.week == args.week,
                    TeamStatsSnapshot.scope == args.scope,
                )
            )
            row = existing or TeamStatsSnapshot(
                team_name=team_name,
                conference=conference,
                season=args.season,
                week=args.week,
                scope=args.scope,
            )
            row.conference = conference
            row.offense_stats = payload["offense"] if isinstance(payload["offense"], dict) else {}
            row.defense_stats = payload["defense"] if isinstance(payload["defense"], dict) else {}
            row.advanced_stats = payload["advanced"] if isinstance(payload["advanced"], dict) else {}
            row.source = "cfbd_api"
            session.add(row)
            upserted += 1
        session.commit()
    finally:
        session.close()

    games_ingested = 0
    if not args.skip_games:
        games_ingested = _ingest_games(client, args.season, conferences, max_week=args.max_week)
    print(f"Upserted {upserted} team stats snapshots for season {args.season}.")
    if args.skip_games:
        print("Skipped game ingest (--skip-games).")
    else:
        print(f"Ingested/updated {games_ingested} games for bye week + standings support.")


if __name__ == "__main__":
    main()
