import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.scoring import calculate_fantasy_points, get_scoring_rules


def _ensure_matchups(session, league_id: int, season: int, week: int, teams: list[Team]) -> list[Matchup]:
    existing = session.scalars(
        select(Matchup).where(
            Matchup.league_id == league_id,
            Matchup.season == season,
            Matchup.week == week,
        )
    ).all()
    if existing:
        return existing

    sorted_teams = sorted(teams, key=lambda team: team.id)
    matchups: list[Matchup] = []
    for index in range(0, len(sorted_teams) - 1, 2):
        home = sorted_teams[index]
        away = sorted_teams[index + 1]
        matchup = Matchup(
            league_id=league_id,
            season=season,
            week=week,
            home_team_id=home.id,
            away_team_id=away.id,
            status="scheduled",
        )
        session.add(matchup)
        matchups.append(matchup)
    session.commit()
    return matchups


def _calculate_team_scores(
    session,
    team_id: int,
    season: int,
    week: int,
    rules: dict[str, dict[str, float] | list[tuple[int, int | None, float]]],
) -> tuple[float, float, float]:
    roster_entries = session.scalars(
        select(RosterEntry).options(selectinload(RosterEntry.player)).where(RosterEntry.team_id == team_id)
    ).all()
    if not roster_entries:
        return 0.0, 0.0, 0.0

    active_entries = [entry for entry in roster_entries if entry.status == "active"]
    if active_entries:
        starters_set = {entry.id for entry in active_entries}
    else:
        starters_set = {entry.id for entry in roster_entries}

    starters_points = 0.0
    bench_points = 0.0

    for entry in roster_entries:
        stat = session.scalar(
            select(PlayerStat).where(
                PlayerStat.player_id == entry.player_id,
                PlayerStat.season == season,
                PlayerStat.week == week,
            )
        )
        if not stat:
            continue
        position = entry.player.position if entry.player else None
        points = calculate_fantasy_points(stat.stats, rules, position=position)
        if entry.id in starters_set:
            starters_points += points
        else:
            bench_points += points

    starters_points = round(starters_points, 2)
    bench_points = round(bench_points, 2)
    total_points = starters_points
    return total_points, starters_points, bench_points


def _upsert_team_week_score(
    session,
    league_id: int,
    team_id: int,
    season: int,
    week: int,
    totals: tuple[float, float, float],
) -> None:
    existing = session.scalar(
        select(TeamWeekScore).where(
            TeamWeekScore.team_id == team_id,
            TeamWeekScore.season == season,
            TeamWeekScore.week == week,
        )
    )
    if existing:
        existing.points_total = totals[0]
        existing.points_starters = totals[1]
        existing.points_bench = totals[2]
        session.add(existing)
    else:
        session.add(
            TeamWeekScore(
                league_id=league_id,
                team_id=team_id,
                season=season,
                week=week,
                points_total=totals[0],
                points_starters=totals[1],
                points_bench=totals[2],
            )
        )


def _update_matchup_scores(
    session, league_id: int, season: int, week: int, final: bool
) -> list[Matchup]:
    matchups = session.scalars(
        select(Matchup).where(
            Matchup.league_id == league_id,
            Matchup.season == season,
            Matchup.week == week,
        )
    ).all()
    score_map = {
        score.team_id: score
        for score in session.scalars(
            select(TeamWeekScore).where(
                TeamWeekScore.league_id == league_id,
                TeamWeekScore.season == season,
                TeamWeekScore.week == week,
            )
        )
    }
    for matchup in matchups:
        home_score = score_map.get(matchup.home_team_id)
        away_score = score_map.get(matchup.away_team_id)
        matchup.home_score = home_score.points_total if home_score else 0.0
        matchup.away_score = away_score.points_total if away_score else 0.0
        matchup.status = "final" if final else "in_progress"
        session.add(matchup)
    session.commit()
    return matchups


def _update_standings(session, league_id: int, season: int, week: int, matchups: list[Matchup]) -> None:
    session.execute(
        delete(Standing).where(
            Standing.league_id == league_id,
            Standing.season == season,
            Standing.week == week,
        )
    )
    session.commit()

    previous_records = {
        row.team_id: row
        for row in session.scalars(
            select(Standing).where(
                Standing.league_id == league_id,
                Standing.season == season,
                Standing.week == week - 1,
            )
        )
    }
    records = defaultdict(
        lambda: {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0}
    )
    for team_id, row in previous_records.items():
        records[team_id] = {
            "wins": row.wins,
            "losses": row.losses,
            "ties": row.ties,
            "points_for": row.points_for,
            "points_against": row.points_against,
        }

    for matchup in matchups:
        home_score = matchup.home_score
        away_score = matchup.away_score
        records[matchup.home_team_id]["points_for"] += home_score
        records[matchup.home_team_id]["points_against"] += away_score
        records[matchup.away_team_id]["points_for"] += away_score
        records[matchup.away_team_id]["points_against"] += home_score

        if home_score > away_score:
            records[matchup.home_team_id]["wins"] += 1
            records[matchup.away_team_id]["losses"] += 1
        elif away_score > home_score:
            records[matchup.away_team_id]["wins"] += 1
            records[matchup.home_team_id]["losses"] += 1
        else:
            records[matchup.home_team_id]["ties"] += 1
            records[matchup.away_team_id]["ties"] += 1

    teams = session.scalars(select(Team).where(Team.league_id == league_id)).all()
    for team in teams:
        record = records[team.id]
        session.add(
            Standing(
                league_id=league_id,
                team_id=team.id,
                season=season,
                week=week,
                wins=record["wins"],
                losses=record["losses"],
                ties=record["ties"],
                points_for=round(record["points_for"], 2),
                points_against=round(record["points_against"], 2),
            )
        )
    session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute weekly fantasy scores and standings.")
    parser.add_argument("--season", type=int, default=datetime.now().year)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--league-id", type=int)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()

    rules = get_scoring_rules()
    session = SessionLocal()
    try:
        leagues = session.scalars(select(League)).all()
        if args.league_id:
            leagues = [league for league in leagues if league.id == args.league_id]

        for league in leagues:
            teams = session.scalars(select(Team).where(Team.league_id == league.id)).all()
            if len(teams) < 2:
                print(f"Skipping league {league.id}: needs at least 2 teams.")
                continue

            _ensure_matchups(session, league.id, args.season, args.week, teams)

            for team in teams:
                totals = _calculate_team_scores(session, team.id, args.season, args.week, rules)
                _upsert_team_week_score(session, league.id, team.id, args.season, args.week, totals)
            session.commit()

            matchups = _update_matchup_scores(session, league.id, args.season, args.week, args.final)

            if args.final:
                _update_standings(session, league.id, args.season, args.week, matchups)

        print("Weekly scoring complete.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
