from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.integrations.cfbd import CFBDClient
from collegefootballfantasy_api.app.integrations.espn import ESPNClient
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.injury_impact import InjuryImpact
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team_stats_snapshot import TeamStatsSnapshot
from collegefootballfantasy_api.app.schemas.stats import (
    TeamInjuriesList,
    TeamInjuryRow,
    TeamStandingRow,
    TeamStandingsList,
    TeamStatsDetail,
    TeamStatsSummary,
    TeamStatsSummaryList,
)
from collegefootballfantasy_api.app.services.power4 import (
    canonical_school_name,
    conference_for_school,
    list_power4_teams,
    resolve_power4_school,
)

router = APIRouter()


def _normalize_conference(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.upper().replace(" ", "")
    if normalized in {"ALL", "ANY"}:
        return None
    return normalized


def _bye_weeks_for_teams(db: Session, season: int, conference: str | None = None) -> dict[str, int | None]:
    teams = list_power4_teams(conference)
    bye_map: dict[str, int | None] = {team: None for team in teams}
    if not teams:
        return bye_map

    weeks_by_team: dict[str, set[int]] = {team: set() for team in teams}
    rows = (
        db.query(Game.home_team, Game.away_team, Game.week)
        .filter(Game.season == season, Game.season_type == "regular", Game.week > 0)
        .all()
    )
    for home_team, away_team, week in rows:
        canonical_home = canonical_school_name(home_team or "")
        canonical_away = canonical_school_name(away_team or "")
        if canonical_home in weeks_by_team:
            weeks_by_team[canonical_home].add(week)
        if canonical_away in weeks_by_team:
            weeks_by_team[canonical_away].add(week)

    for team, played_weeks in weeks_by_team.items():
        if not played_weeks:
            continue
        start_week = min(played_weeks)
        end_week = max(played_weeks)
        missing = sorted(set(range(start_week, end_week + 1)) - played_weeks)
        bye_map[team] = missing[0] if missing else None
    return bye_map


def _int_value(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def _float_value(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _standings_from_cfbd(season: int, conference_key: str) -> list[TeamStandingRow] | None:
    teams = set(list_power4_teams(conference_key))
    if not teams:
        return None
    try:
        rows = CFBDClient().get_records(season=season, conference=conference_key)
    except Exception:
        return None

    sortable: list[tuple[str, int, int, int, int, int, int, float, float, float]] = []
    for row in rows:
        team_name = canonical_school_name(str(row.get("team") or ""))
        if not team_name or team_name not in teams:
            continue
        conf = row.get("conferenceGames") if isinstance(row.get("conferenceGames"), dict) else {}
        total = row.get("total") if isinstance(row.get("total"), dict) else {}

        conf_wins = _int_value(conf.get("wins"))
        conf_losses = _int_value(conf.get("losses"))
        conf_ties = _int_value(conf.get("ties"))
        conf_games = _int_value(conf.get("games"))
        overall_wins = _int_value(total.get("wins"))
        overall_losses = _int_value(total.get("losses"))
        overall_ties = _int_value(total.get("ties"))
        overall_games = _int_value(total.get("games"))

        conf_pct = (conf_wins + (0.5 * conf_ties)) / conf_games if conf_games > 0 else -1.0
        overall_pct = (overall_wins + (0.5 * overall_ties)) / overall_games if overall_games > 0 else -1.0
        expected_wins = _float_value(row.get("expectedWins"), 0.0)

        sortable.append(
            (
                team_name,
                conf_wins,
                conf_losses,
                conf_ties,
                overall_wins,
                overall_losses,
                overall_ties,
                conf_pct,
                overall_pct,
                expected_wins,
            )
        )

    if not sortable:
        return None

    sortable.sort(
        key=lambda item: (
            -item[7],  # conference pct
            -item[1],  # conference wins
            item[2],   # conference losses
            -item[8],  # overall pct
            -item[4],  # overall wins
            item[5],   # overall losses
            -item[9],  # expected wins
            item[0],   # team name
        )
    )

    results: list[TeamStandingRow] = []
    rank = 1
    for team_name, conf_wins, conf_losses, conf_ties, overall_wins, overall_losses, overall_ties, _cp, _op, _ew in sortable:
        has_conf_games = (conf_wins + conf_losses + conf_ties) > 0
        has_overall_games = (overall_wins + overall_losses + overall_ties) > 0
        results.append(
            TeamStandingRow(
                team=team_name,
                conference=conference_key,
                conference_rank=rank if has_conf_games else None,
                conference_wins=conf_wins if has_conf_games else None,
                conference_losses=conf_losses if has_conf_games else None,
                overall_wins=overall_wins if has_overall_games else None,
                overall_losses=overall_losses if has_overall_games else None,
            )
        )
        if has_conf_games:
            rank += 1
    present = {row.team for row in results}
    for team_name in sorted(teams - present):
        results.append(
            TeamStandingRow(
                team=team_name,
                conference=conference_key,
                conference_rank=None,
                conference_wins=None,
                conference_losses=None,
                overall_wins=None,
                overall_losses=None,
            )
        )
    return results


def _parse_record_summary(summary: object) -> tuple[int | None, int | None]:
    if not isinstance(summary, str):
        return None, None
    parts = [part.strip() for part in summary.split("-")]
    if len(parts) < 2:
        return None, None
    try:
        wins = int(parts[0])
        losses = int(parts[1])
        return wins, losses
    except ValueError:
        return None, None


def _standings_from_espn(season: int, conference_key: str) -> list[TeamStandingRow] | None:
    teams = set(list_power4_teams(conference_key))
    if not teams:
        return None

    try:
        page_rows = ESPNClient().get_standings_from_page(season=season, conference=conference_key)
    except Exception:
        page_rows = []

    if page_rows:
        rows_out: list[TeamStandingRow] = []
        seen: set[str] = set()
        for row in page_rows:
            team_name = canonical_school_name(str(row.get("team") or ""))
            if not team_name or team_name not in teams:
                continue
            conf_wins, conf_losses = _parse_record_summary(row.get("conference_record"))
            overall_wins, overall_losses = _parse_record_summary(row.get("overall_record"))
            rank_value = row.get("rank")
            conference_rank = int(rank_value) if isinstance(rank_value, int) else None
            rows_out.append(
                TeamStandingRow(
                    team=team_name,
                    conference=conference_key,
                    conference_rank=conference_rank,
                    conference_wins=conf_wins,
                    conference_losses=conf_losses,
                    overall_wins=overall_wins,
                    overall_losses=overall_losses,
                )
            )
            seen.add(team_name)

        for team_name in sorted(teams - seen):
            rows_out.append(
                TeamStandingRow(
                    team=team_name,
                    conference=conference_key,
                    conference_rank=None,
                    conference_wins=None,
                    conference_losses=None,
                    overall_wins=None,
                    overall_losses=None,
                )
            )
        if rows_out:
            return rows_out

    try:
        entries = ESPNClient().get_standings(season=season, conference=conference_key)
    except Exception:
        return None

    if not entries:
        return None

    rows_out: list[TeamStandingRow] = []
    seen: set[str] = set()
    rank = 1

    for entry in entries:
        team_payload = entry.get("team")
        if not isinstance(team_payload, dict):
            continue
        team_display = (
            team_payload.get("shortDisplayName")
            or team_payload.get("displayName")
            or team_payload.get("location")
            or team_payload.get("name")
        )
        team_name = canonical_school_name(str(team_display or ""))
        if not team_name or team_name not in teams:
            continue

        stats = entry.get("stats") if isinstance(entry.get("stats"), list) else []
        overall_summary = None
        conf_summary = None
        for stat in stats:
            if not isinstance(stat, dict):
                continue
            name = str(stat.get("name") or "").strip().lower()
            abbr = str(stat.get("abbreviation") or "").strip().lower()
            summary = stat.get("summary") or stat.get("displayValue")
            if name == "overall" or abbr == "overall":
                overall_summary = summary
            if name in {"vs. conf.", "vs conf", "vsconf"} or abbr == "conf":
                conf_summary = summary

        overall_wins, overall_losses = _parse_record_summary(overall_summary)
        conf_wins, conf_losses = _parse_record_summary(conf_summary)

        rows_out.append(
            TeamStandingRow(
                team=team_name,
                conference=conference_key,
                conference_rank=rank if conf_wins is not None and conf_losses is not None else None,
                conference_wins=conf_wins,
                conference_losses=conf_losses,
                overall_wins=overall_wins,
                overall_losses=overall_losses,
            )
        )
        seen.add(team_name)
        if conf_wins is not None and conf_losses is not None:
            rank += 1

    for team_name in sorted(teams - seen):
        rows_out.append(
            TeamStandingRow(
                team=team_name,
                conference=conference_key,
                conference_rank=None,
                conference_wins=None,
                conference_losses=None,
                overall_wins=None,
                overall_losses=None,
            )
        )

    return rows_out if rows_out else None


@router.get("/teams", response_model=TeamStatsSummaryList)
def list_power4_team_stats(
    season: int,
    conference: str | None = None,
    db: Session = Depends(get_db),
) -> TeamStatsSummaryList:
    conference_key = _normalize_conference(conference)
    team_names = list_power4_teams(conference_key)
    bye_map = _bye_weeks_for_teams(db, season, conference_key)

    snapshot_rows = (
        db.query(TeamStatsSnapshot)
        .filter(
            TeamStatsSnapshot.season == season,
            TeamStatsSnapshot.scope == "season",
            TeamStatsSnapshot.week == 0,
        )
        .all()
    )
    snapshots = {row.team_name: row for row in snapshot_rows}

    data = []
    for team in team_names:
        conference_name = conference_for_school(team)
        if conference_key and conference_name != conference_key:
            continue
        snapshot = snapshots.get(team)
        data.append(
            TeamStatsSummary(
                team=team,
                conference=conference_name or "UNKNOWN",
                bye_week=bye_map.get(team),
                has_offense_data=bool(snapshot and snapshot.offense_stats),
                has_defense_data=bool(snapshot and snapshot.defense_stats),
                has_advanced_data=bool(snapshot and snapshot.advanced_stats),
                updated_at=snapshot.updated_at if snapshot else None,
            )
        )
    return TeamStatsSummaryList(data=data, total=len(data))


@router.get("/team/{team_name}", response_model=TeamStatsDetail)
def get_power4_team_stats(
    team_name: str,
    season: int,
    db: Session = Depends(get_db),
) -> TeamStatsDetail:
    canonical_name = canonical_school_name(team_name) or team_name
    conference = conference_for_school(canonical_name)
    if not conference:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team is not in the power 4")

    snapshot = (
        db.query(TeamStatsSnapshot)
        .filter(
            TeamStatsSnapshot.team_name == canonical_name,
            TeamStatsSnapshot.season == season,
            TeamStatsSnapshot.scope == "season",
            TeamStatsSnapshot.week == 0,
        )
        .first()
    )
    bye_week = _bye_weeks_for_teams(db, season, conference).get(canonical_name)
    return TeamStatsDetail(
        team=canonical_name,
        conference=conference,
        season=season,
        week=0,
        bye_week=bye_week,
        offense=snapshot.offense_stats if snapshot else {},
        defense=snapshot.defense_stats if snapshot else {},
        advanced=snapshot.advanced_stats if snapshot else {},
        last_updated=snapshot.updated_at if snapshot else None,
    )


@router.get("/standings", response_model=TeamStandingsList)
def get_power4_standings(
    season: int,
    conference: str,
    db: Session = Depends(get_db),
) -> TeamStandingsList:
    conference_key = _normalize_conference(conference)
    teams = list_power4_teams(conference_key)
    if not teams:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid conference")

    espn_rows = _standings_from_espn(season, conference_key)
    if espn_rows is not None:
        return TeamStandingsList(data=espn_rows, total=len(espn_rows))

    cfbd_rows = _standings_from_cfbd(season, conference_key)
    if cfbd_rows is not None:
        return TeamStandingsList(data=cfbd_rows, total=len(cfbd_rows))

    records: dict[str, dict[str, int]] = {
        team: {"ow": 0, "ol": 0, "ot": 0, "cw": 0, "cl": 0, "ct": 0, "overall_games": 0, "conference_games": 0}
        for team in teams
    }
    rows = (
        db.query(Game.home_team, Game.away_team, Game.home_points, Game.away_points)
        .filter(
            Game.season == season,
            Game.season_type == "regular",
            Game.week > 0,
            Game.home_points.isnot(None),
            Game.away_points.isnot(None),
        )
        .all()
    )

    for home_team, away_team, home_points, away_points in rows:
        home_name = canonical_school_name(home_team or "")
        away_name = canonical_school_name(away_team or "")
        home_conf = conference_for_school(home_name or "")
        away_conf = conference_for_school(away_name or "")
        home_in_scope = home_name in records
        away_in_scope = away_name in records

        if not home_in_scope and not away_in_scope:
            continue

        if home_in_scope:
            records[home_name]["overall_games"] += 1
        if away_in_scope:
            records[away_name]["overall_games"] += 1

        if home_points > away_points:
            if home_in_scope:
                records[home_name]["ow"] += 1
            if away_in_scope:
                records[away_name]["ol"] += 1
        elif away_points > home_points:
            if away_in_scope:
                records[away_name]["ow"] += 1
            if home_in_scope:
                records[home_name]["ol"] += 1
        else:
            if home_in_scope:
                records[home_name]["ot"] += 1
            if away_in_scope:
                records[away_name]["ot"] += 1

        if home_conf == conference_key and away_conf == conference_key and home_in_scope and away_in_scope:
            records[home_name]["conference_games"] += 1
            records[away_name]["conference_games"] += 1
            if home_points > away_points:
                records[home_name]["cw"] += 1
                records[away_name]["cl"] += 1
            elif away_points > home_points:
                records[away_name]["cw"] += 1
                records[home_name]["cl"] += 1
            else:
                records[home_name]["ct"] += 1
                records[away_name]["ct"] += 1

    sortable = []
    for team in teams:
        rec = records[team]
        conference_games = rec["conference_games"]
        overall_games = rec["overall_games"]
        conference_pct = (
            (rec["cw"] + (0.5 * rec["ct"])) / conference_games
            if conference_games > 0
            else -1.0
        )
        overall_pct = (
            (rec["ow"] + (0.5 * rec["ot"])) / overall_games
            if overall_games > 0
            else -1.0
        )
        sortable.append(
            (
                team,
                rec["cw"],
                rec["cl"],
                rec["ct"],
                rec["ow"],
                rec["ol"],
                rec["ot"],
                conference_games,
                overall_games,
                conference_pct,
                overall_pct,
            )
        )
    sortable.sort(
        key=lambda item: (
            -item[9],  # conference win pct
            -item[1],  # conference wins
            item[2],   # conference losses
            -item[10], # overall win pct
            -item[4],  # overall wins
            item[5],   # overall losses
            item[0],   # team name
        )
    )

    rows_out: list[TeamStandingRow] = []
    rank = 1
    for team, cw, cl, _ct, ow, ol, _ot, conference_games, overall_games, _cp, _op in sortable:
        rows_out.append(
            TeamStandingRow(
                team=team,
                conference=conference_key,
                conference_rank=rank if conference_games > 0 else None,
                conference_wins=cw if conference_games > 0 else None,
                conference_losses=cl if conference_games > 0 else None,
                overall_wins=ow if overall_games > 0 else None,
                overall_losses=ol if overall_games > 0 else None,
            )
        )
        if conference_games > 0:
            rank += 1
    return TeamStandingsList(data=rows_out, total=len(rows_out))


@router.get("/injuries", response_model=TeamInjuriesList)
def list_power4_injuries(
    season: int,
    week: int,
    conference: str | None = None,
    team: str | None = None,
    db: Session = Depends(get_db),
) -> TeamInjuriesList:
    conference_key = _normalize_conference(conference)
    query = db.query(Injury, Player).join(Player, Injury.player_id == Player.id)
    query = query.filter(Injury.season == season, Injury.week == week)
    if team:
        query = query.filter(Player.school.ilike(f"%{team}%"))
    rows = query.order_by(Injury.updated_at.desc()).all()

    impacts = {
        impact.player_id: impact.delta_fpts
        for impact in db.query(InjuryImpact)
        .filter(InjuryImpact.season == season, InjuryImpact.week == week)
        .all()
    }

    data: list[TeamInjuryRow] = []
    for injury, player in rows:
        canonical_team = resolve_power4_school(player.school or "")
        conference_name = conference_for_school(canonical_team or player.school)
        if not conference_name:
            continue
        if conference_key and conference_name != conference_key:
            continue
        data.append(
            TeamInjuryRow(
                player_id=player.id,
                player_name=player.name,
                team=canonical_team or player.school,
                conference=conference_name,
                position=player.position,
                status=injury.status,
                injury=injury.injury,
                return_timeline=injury.return_timeline,
                practice_level=injury.practice_level,
                notes=injury.notes,
                last_updated=injury.updated_at or datetime.utcnow(),
                projection_delta=impacts.get(player.id),
            )
        )
    return TeamInjuriesList(data=data, total=len(data))
