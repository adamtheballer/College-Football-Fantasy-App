from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.lineup_week_snapshot import LineupWeekSnapshot
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.scoring_run import ScoringRun
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.services.player_lock_service import as_utc, game_starts_for_players


DEFAULT_SCORING_RULES = {
    "pass_yards": 0.04,
    "pass_tds": 4,
    "interceptions": -2,
    "rush_yards": 0.1,
    "rush_tds": 6,
    "receptions": 1,
    "rec_yards": 0.1,
    "rec_tds": 6,
    "fumbles_lost": -2,
    "fg_made_0_39": 3,
    "fg_made_40_49": 4,
    "fg_made_50_plus": 5,
    "xp_made": 1,
}

SCORING_RULE_ALIASES = {
    "ppr": "receptions",
    "pass_td": "pass_tds",
    "passing_td": "pass_tds",
    "passing_tds": "pass_tds",
    "rush_td": "rush_tds",
    "rushing_td": "rush_tds",
    "rushing_tds": "rush_tds",
    "rec_td": "rec_tds",
    "receiving_td": "rec_tds",
    "receiving_tds": "rec_tds",
    "pass_yd": "pass_yards",
    "passing_yards": "pass_yards",
    "rush_yd": "rush_yards",
    "rushing_yards": "rush_yards",
    "receiving_yards": "rec_yards",
    "interception": "interceptions",
    "int": "interceptions",
    "fumble_lost": "fumbles_lost",
    "fg": "fg_made_0_39",
    "xp": "xp_made",
}

SCORING_YARDS_PER_POINT_ALIASES = {
    "pass_yds_per_pt": "pass_yards",
    "rush_yds_per_pt": "rush_yards",
    "rec_yds_per_pt": "rec_yards",
}

STAT_FIELD_ALIASES = {
    "pass_yards": ["pass_yards", "PassingYards", "passing_yards", "PassYards", "PassingYardage"],
    "pass_tds": ["pass_tds", "PassingTouchdowns", "PassingTD", "passing_tds", "PassTD"],
    "interceptions": ["interceptions", "PassingInterceptions", "Interceptions", "passing_interceptions"],
    "rush_yards": ["rush_yards", "RushingYards", "rushing_yards", "RushYards"],
    "rush_tds": ["rush_tds", "RushingTouchdowns", "RushingTD", "rushing_tds", "RushTD"],
    "receptions": ["receptions", "Receptions", "ReceivingReceptions", "Rec"],
    "rec_yards": ["rec_yards", "ReceivingYards", "receiving_yards", "ReceivingYardage"],
    "rec_tds": ["rec_tds", "ReceivingTouchdowns", "ReceivingTD", "receiving_tds", "RecTD"],
    "fumbles_lost": ["fumbles_lost", "FumblesLost", "fumblesLost"],
    "fg_made_0_39": ["fg_made_0_39", "FieldGoalsMade0to39", "FieldGoalsMade0To39", "FgMade0To39"],
    "fg_made_40_49": ["fg_made_40_49", "FieldGoalsMade40to49", "FieldGoalsMade40To49", "FgMade40To49"],
    "fg_made_50_plus": ["fg_made_50_plus", "FieldGoalsMade50Plus", "FieldGoalsMade50", "FgMade50Plus"],
    "xp_made": ["xp_made", "ExtraPointsMade", "ExtraPoints", "XpMade"],
}

BENCH_SLOTS = {"BE", "BENCH"}
NON_SCORING_SLOTS = {"IR", "INJURED_RESERVE"}
FINAL_MATCHUP_STATUSES = {"final", "stat_corrected"}
DELAYED_SCORE_STATUSES = {"delayed", "unavailable", "stale"}


@dataclass(frozen=True)
class ScoringSummary:
    players_scored: int
    teams_scored: int
    matchups_updated: int
    standings_updated: int


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _first_number(raw_stats: dict[str, Any], aliases: list[str]) -> float:
    for key in aliases:
        if key in raw_stats:
            return _number(raw_stats.get(key))
    lower_map = {str(key).lower(): value for key, value in raw_stats.items()}
    for key in aliases:
        value = lower_map.get(key.lower())
        if value is not None:
            return _number(value)
    return 0.0


def normalize_player_stats(raw_stats: dict) -> dict:
    return {
        stat_key: _first_number(raw_stats or {}, aliases)
        for stat_key, aliases in STAT_FIELD_ALIASES.items()
    }


def normalize_scoring_rules(scoring_rules: dict | None) -> dict[str, float]:
    normalized = DEFAULT_SCORING_RULES.copy()
    for key, value in (scoring_rules or {}).items():
        raw_key = str(key)
        if raw_key in SCORING_YARDS_PER_POINT_ALIASES:
            yards_per_point = _number(value)
            if yards_per_point > 0:
                normalized[SCORING_YARDS_PER_POINT_ALIASES[raw_key]] = round(1 / yards_per_point, 6)
            continue
        canonical_key = SCORING_RULE_ALIASES.get(raw_key, raw_key)
        if canonical_key in normalized:
            normalized[canonical_key] = _number(value)
    return normalized


def calculate_player_fantasy_points(
    normalized_stats: dict,
    scoring_rules: dict,
) -> tuple[float, dict]:
    rules = normalize_scoring_rules(scoring_rules)
    breakdown: dict[str, dict[str, float] | float] = {}
    total = 0.0
    for key, multiplier in rules.items():
        stat = _number(normalized_stats.get(key))
        points = round(stat * multiplier, 4)
        breakdown[key] = {
            "stat": stat,
            "multiplier": multiplier,
            "points": points,
        }
        total += points
    rounded_total = round(total, 2)
    breakdown["total"] = rounded_total
    return rounded_total, breakdown


def is_starting_slot(slot: str) -> bool:
    normalized = (slot or "").upper()
    return normalized not in BENCH_SLOTS and normalized not in NON_SCORING_SLOTS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _league_settings(db: Session, league_id: int) -> LeagueSettings | None:
    return db.query(LeagueSettings).filter(LeagueSettings.league_id == league_id).first()


def create_or_refresh_lineup_snapshots(db: Session, league_id: int, season: int, week: int) -> int:
    existing = {
        (snapshot.team_id, snapshot.player_id): snapshot
        for snapshot in db.query(LineupWeekSnapshot)
        .filter(
            LineupWeekSnapshot.league_id == league_id,
            LineupWeekSnapshot.season == season,
            LineupWeekSnapshot.week == week,
        )
        .all()
    }
    roster_entries = (
        db.query(RosterEntry)
        .filter(RosterEntry.league_id == league_id)
        .order_by(RosterEntry.team_id.asc(), RosterEntry.id.asc())
        .all()
    )
    now = _now()
    player_ids = {entry.player_id for entry in roster_entries}
    game_starts = game_starts_for_players(db, player_ids=player_ids, season=season, week=week)
    current_keys = {(entry.team_id, entry.player_id) for entry in roster_entries}
    created = 0
    for entry in roster_entries:
        game_start_at = game_starts.get(entry.player_id)
        snapshot = existing.get((entry.team_id, entry.player_id))
        if snapshot and snapshot.locked_at is not None:
            continue
        if snapshot is None:
            snapshot = LineupWeekSnapshot(
                league_id=league_id,
                team_id=entry.team_id,
                player_id=entry.player_id,
                season=season,
                week=week,
                slot=(entry.slot or "BENCH").upper(),
                is_starter=is_starting_slot(entry.slot or ""),
                game_start_at=game_start_at,
                locked_at=as_utc(now) if game_start_at is not None and game_start_at <= as_utc(now) else None,
            )
            db.add(snapshot)
            created += 1
            continue
        snapshot.slot = (entry.slot or "BENCH").upper()
        snapshot.is_starter = is_starting_slot(entry.slot or "")
        snapshot.game_start_at = game_start_at
        if game_start_at is not None and game_start_at <= as_utc(now):
            snapshot.locked_at = as_utc(now)

    for key, snapshot in existing.items():
        if key not in current_keys and snapshot.locked_at is None:
            db.delete(snapshot)
    if created or existing:
        db.flush()
    return created


def _stat_map(db: Session, season: int, week: int, player_ids: set[int]) -> dict[int, PlayerStat]:
    if not player_ids:
        return {}
    rows = (
        db.query(PlayerStat)
        .filter(
            PlayerStat.season == season,
            PlayerStat.week == week,
            PlayerStat.player_id.in_(player_ids),
        )
        .all()
    )
    return {row.player_id: row for row in rows}


def _relevant_scoring_player_ids(db: Session, league_id: int, season: int, week: int) -> set[int]:
    snapshot_ids = {
        player_id
        for (player_id,) in db.query(LineupWeekSnapshot.player_id)
        .filter(
            LineupWeekSnapshot.league_id == league_id,
            LineupWeekSnapshot.season == season,
            LineupWeekSnapshot.week == week,
        )
        .all()
    }
    existing_score_ids = {
        player_id
        for (player_id,) in db.query(PlayerWeekScore.player_id)
        .filter(
            PlayerWeekScore.league_id == league_id,
            PlayerWeekScore.season == season,
            PlayerWeekScore.week == week,
        )
        .all()
    }
    return snapshot_ids | existing_score_ids


def recalculate_player_week_scores(db: Session, league_id: int, season: int, week: int) -> int:
    settings = _league_settings(db, league_id)
    scoring_rules = settings.scoring_json if settings else {}
    player_ids = _relevant_scoring_player_ids(db, league_id, season, week)
    stat_by_player = _stat_map(db, season, week, player_ids)
    if player_ids and not stat_by_player:
        raise ValueError(
            f"no provider stat rows found for league {league_id}, season {season}, week {week}; refusing to overwrite scores"
        )
    score_by_player = {
        row.player_id: row
        for row in db.query(PlayerWeekScore)
        .filter(
            PlayerWeekScore.league_id == league_id,
            PlayerWeekScore.season == season,
            PlayerWeekScore.week == week,
            PlayerWeekScore.player_id.in_(player_ids or {0}),
        )
        .all()
    }
    calculated_at = _now()
    scored = 0
    for player_id in sorted(player_ids):
        stat_row = stat_by_player.get(player_id)
        score = score_by_player.get(player_id)
        if not stat_row:
            if score:
                stale_breakdown = {
                    **(score.breakdown_json or {}),
                    "status": "stale",
                    "message": "No provider stat row was available for this recalculation; previous score retained.",
                }
                if score.status != "stale" or score.breakdown_json != stale_breakdown:
                    score.status = "stale"
                    score.breakdown_json = stale_breakdown
                    score.calculated_at = calculated_at
            continue
        normalized_stats = normalize_player_stats(stat_row.stats)
        fantasy_points, breakdown = calculate_player_fantasy_points(normalized_stats, scoring_rules)
        score_changed = False
        if not score:
            score = PlayerWeekScore(
                league_id=league_id,
                player_id=player_id,
                season=season,
                week=week,
            )
            db.add(score)
            score_by_player[player_id] = score
            score_changed = True
        if (
            score.fantasy_points != fantasy_points
            or score.status != "live"
            or score.breakdown_json != breakdown
            or score.source_stat_id != stat_row.id
        ):
            score_changed = True
        if score_changed:
            score.fantasy_points = fantasy_points
            score.status = "live"
            score.breakdown_json = breakdown
            score.source_stat_id = stat_row.id
            score.calculated_at = calculated_at
        scored += 1
    if scored:
        db.flush()
    return scored


def recalculate_team_week_score(db: Session, league_id: int, team_id: int, season: int, week: int) -> TeamWeekScore:
    snapshots = (
        db.query(LineupWeekSnapshot)
        .filter(
            LineupWeekSnapshot.league_id == league_id,
            LineupWeekSnapshot.team_id == team_id,
            LineupWeekSnapshot.season == season,
            LineupWeekSnapshot.week == week,
        )
        .all()
    )
    score_by_player = {
        row.player_id: row
        for row in db.query(PlayerWeekScore)
        .filter(
            PlayerWeekScore.league_id == league_id,
            PlayerWeekScore.season == season,
            PlayerWeekScore.week == week,
            PlayerWeekScore.player_id.in_({snapshot.player_id for snapshot in snapshots} or {0}),
        )
        .all()
    }
    starter_points = 0.0
    bench_points = 0.0
    player_breakdown = []
    missing_starter_scores = 0
    missing_bench_scores = 0
    for snapshot in snapshots:
        score = score_by_player.get(snapshot.player_id)
        points = float(score.fantasy_points if score else 0.0)
        slot = (snapshot.slot or "").upper()
        score_status = score.status if score else "unavailable"
        if snapshot.is_starter:
            starter_points += points
            if not score or score_status in DELAYED_SCORE_STATUSES:
                missing_starter_scores += 1
        elif slot not in NON_SCORING_SLOTS:
            bench_points += points
            if not score or score_status in DELAYED_SCORE_STATUSES:
                missing_bench_scores += 1
        player_breakdown.append(
            {
                "player_id": snapshot.player_id,
                "slot": slot,
                "is_starter": snapshot.is_starter,
                "points": round(points, 2),
                "status": score_status,
            }
        )
    team_score = (
        db.query(TeamWeekScore)
        .filter(
            TeamWeekScore.league_id == league_id,
            TeamWeekScore.team_id == team_id,
            TeamWeekScore.season == season,
            TeamWeekScore.week == week,
        )
        .first()
    )
    is_new = team_score is None
    if team_score is None:
        team_score = TeamWeekScore(
            league_id=league_id,
            team_id=team_id,
            season=season,
            week=week,
        )
        db.add(team_score)
    starter_points = round(starter_points, 2)
    bench_points = round(bench_points, 2)
    breakdown = {
        "players": player_breakdown,
        "starter_points": starter_points,
        "bench_points": bench_points,
        "total_points": starter_points,
        "missing_starter_scores": missing_starter_scores,
        "missing_bench_scores": missing_bench_scores,
    }
    if not snapshots:
        score_status = "unavailable"
    elif missing_starter_scores:
        score_status = "delayed"
    else:
        score_status = "live"
    changed = is_new or any(
        (
            team_score.starter_points != starter_points,
            team_score.bench_points != bench_points,
            team_score.total_points != starter_points,
            team_score.points_starters != starter_points,
            team_score.points_bench != bench_points,
            team_score.points_total != starter_points,
            team_score.breakdown_json != breakdown,
            team_score.status != score_status,
        )
    )
    if changed:
        team_score.starter_points = starter_points
        team_score.bench_points = bench_points
        team_score.total_points = starter_points
        team_score.points_starters = starter_points
        team_score.points_bench = bench_points
        team_score.points_total = starter_points
        team_score.breakdown_json = breakdown
        team_score.status = score_status
        team_score.calculated_at = _now()
        db.flush()
    return team_score


def recalculate_team_week_scores(db: Session, league_id: int, season: int, week: int) -> int:
    team_ids = [
        team_id
        for (team_id,) in db.query(Team.id)
        .filter(Team.league_id == league_id)
        .order_by(Team.id.asc())
        .all()
    ]
    for team_id in team_ids:
        recalculate_team_week_score(db, league_id, team_id, season, week)
    return len(team_ids)


def _team_score_map(db: Session, league_id: int, season: int, week: int) -> dict[int, TeamWeekScore]:
    rows = (
        db.query(TeamWeekScore)
        .filter(
            TeamWeekScore.league_id == league_id,
            TeamWeekScore.season == season,
            TeamWeekScore.week == week,
        )
        .all()
    )
    return {row.team_id: row for row in rows}


def recalculate_matchup_scores(db: Session, league_id: int, season: int, week: int) -> int:
    score_by_team = _team_score_map(db, league_id, season, week)
    matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league_id, Matchup.season == season, Matchup.week == week)
        .all()
    )
    updated = 0
    for matchup in matchups:
        home_score = score_by_team.get(matchup.home_team_id)
        away_score = score_by_team.get(matchup.away_team_id)
        home_points = float(home_score.total_points if home_score else 0.0)
        away_points = float(away_score.total_points if away_score else 0.0)
        next_status = matchup.status
        if (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
            team_statuses = {home_score.status if home_score else "unavailable", away_score.status if away_score else "unavailable"}
            if "unavailable" in team_statuses:
                next_status = "unavailable"
            elif team_statuses.intersection(DELAYED_SCORE_STATUSES):
                next_status = "delayed"
            else:
                next_status = "live"
        if matchup.home_score != home_points or matchup.away_score != away_points or matchup.status != next_status:
            matchup.home_score = home_points
            matchup.away_score = away_points
            matchup.status = next_status
            updated += 1
    if updated:
        db.flush()
    return updated


def _upsert_standing(
    db: Session,
    league_id: int,
    team_id: int,
    season: int,
    week: int,
    wins: int,
    losses: int,
    ties: int,
    points_for: float,
    points_against: float,
) -> Standing:
    standing = (
        db.query(Standing)
        .filter(
            Standing.league_id == league_id,
            Standing.team_id == team_id,
            Standing.season == season,
            Standing.week == week,
        )
        .first()
    )
    if not standing:
        standing = Standing(league_id=league_id, team_id=team_id, season=season, week=week)
        db.add(standing)
    standing.wins = wins
    standing.losses = losses
    standing.ties = ties
    standing.points_for = round(points_for, 2)
    standing.points_against = round(points_against, 2)
    return standing


def recalculate_standings_for_week(db: Session, league_id: int, season: int, week: int) -> int:
    teams = db.query(Team).filter(Team.league_id == league_id).all()
    records = {
        team.id: {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0}
        for team in teams
    }
    final_matchups = (
        db.query(Matchup)
        .filter(Matchup.league_id == league_id, Matchup.season == season, Matchup.week <= week)
        .all()
    )
    for matchup in final_matchups:
        if (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
            continue
        home = records.setdefault(matchup.home_team_id, {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0})
        away = records.setdefault(matchup.away_team_id, {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0, "points_against": 0.0})
        home_score = float(matchup.home_score or 0.0)
        away_score = float(matchup.away_score or 0.0)
        home["points_for"] += home_score
        home["points_against"] += away_score
        away["points_for"] += away_score
        away["points_against"] += home_score
        if home_score > away_score:
            home["wins"] += 1
            away["losses"] += 1
        elif away_score > home_score:
            away["wins"] += 1
            home["losses"] += 1
        else:
            home["ties"] += 1
            away["ties"] += 1
    for team_id, record in records.items():
        _upsert_standing(
            db,
            league_id,
            team_id,
            season,
            week,
            int(record["wins"]),
            int(record["losses"]),
            int(record["ties"]),
            float(record["points_for"]),
            float(record["points_against"]),
        )
    if records:
        db.flush()
    return len(records)


def recalculate_league_week_scores(db: Session, league_id: int, season: int, week: int) -> ScoringSummary:
    create_or_refresh_lineup_snapshots(db, league_id, season, week)
    players_scored = recalculate_player_week_scores(db, league_id, season, week)
    teams_scored = recalculate_team_week_scores(db, league_id, season, week)
    matchups_updated = recalculate_matchup_scores(db, league_id, season, week)
    standings_updated = recalculate_standings_for_week(db, league_id, season, week)
    return ScoringSummary(
        players_scored=players_scored,
        teams_scored=teams_scored,
        matchups_updated=matchups_updated,
        standings_updated=standings_updated,
    )


def run_league_scoring_recalculation(
    db: Session,
    league_id: int | None,
    season: int,
    week: int,
    provider: str = "manual",
) -> ScoringSummary:
    run = ScoringRun(
        league_id=league_id,
        season=season,
        week=week,
        provider=provider,
        status="running",
        started_at=_now(),
    )
    db.add(run)
    db.flush()
    try:
        with db.begin_nested():
            if league_id is not None:
                if not db.get(League, league_id):
                    raise ValueError(f"league {league_id} not found")
                summary = recalculate_league_week_scores(db, league_id, season, week)
            else:
                summary = ScoringSummary(0, 0, 0, 0)
                leagues = db.query(League).filter(League.season_year == season).all()
                for league in leagues:
                    current = recalculate_league_week_scores(db, league.id, season, week)
                    summary = ScoringSummary(
                        players_scored=summary.players_scored + current.players_scored,
                        teams_scored=summary.teams_scored + current.teams_scored,
                        matchups_updated=summary.matchups_updated + current.matchups_updated,
                        standings_updated=summary.standings_updated + current.standings_updated,
                    )
        run.status = "success"
        run.completed_at = _now()
        run.players_updated = summary.players_scored
        run.teams_updated = summary.teams_scored
        run.matchups_updated = summary.matchups_updated
        db.commit()
        return summary
    except Exception as exc:
        run.status = "failed"
        run.completed_at = _now()
        run.error_message = str(exc)[:1000]
        db.commit()
        raise
