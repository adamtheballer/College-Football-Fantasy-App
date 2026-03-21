from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased

from collegefootballfantasy_api.app.api.deps import get_current_user
from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.defense_vs_position import DefenseVsPosition
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.notification import NotificationLog
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.insights import (
    AccoladesResponse,
    DynastyCareerResponse,
    PlayerCompareRequest,
    PlayerCompareResponse,
    PlayerCompareSide,
    RivalryList,
    RivalryRow,
    UserAnalyticsList,
    UserAnalyticsRow,
)
from collegefootballfantasy_api.app.services.matchup_grades import build_matchup_row

router = APIRouter()


def _notification_log_user_filter(user_id: int):
    return or_(
        NotificationLog.user_id == user_id,
        and_(NotificationLog.user_id.is_(None), NotificationLog.user_key == str(user_id)),
    )


def _build_user_matchup_stats(db: Session) -> dict[int, dict[str, float | int]]:
    home_team = aliased(Team)
    away_team = aliased(Team)
    rows = (
        db.query(
            Matchup.id,
            Matchup.league_id,
            Matchup.season,
            Matchup.week,
            Matchup.home_score,
            Matchup.away_score,
            home_team.owner_user_id.label("home_user_id"),
            away_team.owner_user_id.label("away_user_id"),
        )
        .join(home_team, home_team.id == Matchup.home_team_id)
        .join(away_team, away_team.id == Matchup.away_team_id)
        .all()
    )
    user_stats: dict[int, dict[str, float | int]] = defaultdict(
        lambda: {
            "wins": 0,
            "losses": 0,
            "matchups_played": 0,
            "points_for": 0.0,
            "points_against": 0.0,
        }
    )
    for row in rows:
        home_user_id = row.home_user_id
        away_user_id = row.away_user_id
        if not home_user_id or not away_user_id or home_user_id == away_user_id:
            continue

        home_score = float(row.home_score or 0.0)
        away_score = float(row.away_score or 0.0)

        home_record = user_stats[home_user_id]
        away_record = user_stats[away_user_id]
        home_record["matchups_played"] += 1
        away_record["matchups_played"] += 1
        home_record["points_for"] += home_score
        home_record["points_against"] += away_score
        away_record["points_for"] += away_score
        away_record["points_against"] += home_score

        if home_score > away_score:
            home_record["wins"] += 1
            away_record["losses"] += 1
        elif away_score > home_score:
            away_record["wins"] += 1
            home_record["losses"] += 1
    return user_stats


def _championships_by_user(db: Session) -> dict[int, int]:
    home_team = aliased(Team)
    away_team = aliased(Team)
    rows = (
        db.query(
            Matchup.league_id,
            Matchup.season,
            Matchup.home_score,
            Matchup.away_score,
            home_team.owner_user_id.label("home_user_id"),
            away_team.owner_user_id.label("away_user_id"),
        )
        .join(home_team, home_team.id == Matchup.home_team_id)
        .join(away_team, away_team.id == Matchup.away_team_id)
        .all()
    )
    points_by_league_season: dict[tuple[int, int], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        key = (row.league_id, row.season)
        if row.home_user_id:
            points_by_league_season[key][row.home_user_id] += float(row.home_score or 0.0)
        if row.away_user_id:
            points_by_league_season[key][row.away_user_id] += float(row.away_score or 0.0)

    championships: dict[int, int] = defaultdict(int)
    for _key, score_map in points_by_league_season.items():
        if not score_map:
            continue
        winner_id = max(score_map.items(), key=lambda item: item[1])[0]
        championships[winner_id] += 1
    return championships


def _dynasty_power(
    wins: int,
    losses: int,
    championships: int,
    total_points: float,
    league_count: int,
    trades_completed: int,
) -> float:
    games = max(1, wins + losses)
    win_pct = wins / games
    championship_component = min(1.0, championships / max(1, league_count))
    points_component = min(1.0, total_points / max(1.0, games * 140.0))
    trades_component = min(1.0, trades_completed / 20.0)
    score = (
        (win_pct * 45.0)
        + (championship_component * 25.0)
        + (points_component * 20.0)
        + (trades_component * 10.0)
    )
    return round(score, 2)


@router.get("/accolades", response_model=AccoladesResponse)
def get_accolades(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AccoladesResponse:
    user_stats = _build_user_matchup_stats(db)
    stats = user_stats.get(current_user.id, {})
    wins = int(stats.get("wins", 0))
    losses = int(stats.get("losses", 0))
    matchups_played = int(stats.get("matchups_played", 0))
    points_for = float(stats.get("points_for", 0.0))
    leagues_joined = (
        db.query(Team.league_id)
        .filter(Team.owner_user_id == current_user.id)
        .distinct()
        .count()
    )
    championships = _championships_by_user(db).get(current_user.id, 0)
    trades_sent = (
        db.query(NotificationLog)
        .filter(
            and_(
                _notification_log_user_filter(current_user.id),
                or_(
                    NotificationLog.alert_type == "TRADE",
                    NotificationLog.alert_type == "TRADE_SENT",
                    NotificationLog.alert_type == "TRADE_ACCEPTED",
                ),
            )
        )
        .count()
    )
    now = datetime.now(UTC)
    created_at = current_user.created_at if current_user.created_at.tzinfo else current_user.created_at.replace(tzinfo=UTC)
    time_on_app_hours = max(0.0, round((now - created_at).total_seconds() / 3600, 1))

    all_user_rows = db.query(User.id).all()
    power_scores: list[tuple[int, float]] = []
    championships_map = _championships_by_user(db)
    for row in all_user_rows:
        uid = row.id
        row_stats = user_stats.get(uid, {})
        row_wins = int(row_stats.get("wins", 0))
        row_losses = int(row_stats.get("losses", 0))
        row_points_for = float(row_stats.get("points_for", 0.0))
        row_leagues = db.query(Team.league_id).filter(Team.owner_user_id == uid).distinct().count()
        row_trades = (
            db.query(NotificationLog)
            .filter(
                and_(
                    _notification_log_user_filter(uid),
                    or_(
                        NotificationLog.alert_type == "TRADE",
                        NotificationLog.alert_type == "TRADE_SENT",
                        NotificationLog.alert_type == "TRADE_ACCEPTED",
                    ),
                )
            )
            .count()
        )
        power_scores.append(
            (
                uid,
                _dynasty_power(
                    wins=row_wins,
                    losses=row_losses,
                    championships=championships_map.get(uid, 0),
                    total_points=row_points_for,
                    league_count=row_leagues,
                    trades_completed=row_trades,
                ),
            )
        )
    power_scores.sort(key=lambda item: item[1], reverse=True)
    rank_lookup = {uid: idx + 1 for idx, (uid, _score) in enumerate(power_scores)}
    global_rank = rank_lookup.get(current_user.id)
    global_percentile = None
    if global_rank is not None and power_scores:
        global_percentile = round((1 - ((global_rank - 1) / len(power_scores))) * 100, 2)

    return AccoladesResponse(
        user_id=current_user.id,
        first_name=current_user.first_name,
        time_on_app_hours=time_on_app_hours,
        trades_sent=trades_sent,
        matchups_won=wins,
        matchups_played=matchups_played,
        global_rank=global_rank,
        global_percentile=global_percentile,
    )


@router.get("/dynasty", response_model=DynastyCareerResponse)
def get_dynasty_career(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DynastyCareerResponse:
    user_stats = _build_user_matchup_stats(db).get(current_user.id, {})
    wins = int(user_stats.get("wins", 0))
    losses = int(user_stats.get("losses", 0))
    points_for = float(user_stats.get("points_for", 0.0))
    games = max(1, wins + losses)
    leagues_played = (
        db.query(League.id)
        .join(Team, Team.league_id == League.id)
        .filter(Team.owner_user_id == current_user.id)
        .distinct()
        .count()
    )
    years_played = (
        db.query(League.season_year)
        .join(Team, Team.league_id == League.id)
        .filter(Team.owner_user_id == current_user.id)
        .distinct()
        .count()
    )
    championships = _championships_by_user(db).get(current_user.id, 0)
    trades_completed = (
        db.query(NotificationLog)
        .filter(
            and_(
                _notification_log_user_filter(current_user.id),
                or_(
                    NotificationLog.alert_type == "TRADE_ACCEPTED",
                    NotificationLog.alert_type == "TRADE",
                ),
            )
        )
        .count()
    )
    power = _dynasty_power(
        wins=wins,
        losses=losses,
        championships=championships,
        total_points=points_for,
        league_count=leagues_played,
        trades_completed=trades_completed,
    )
    return DynastyCareerResponse(
        user_id=current_user.id,
        championships=championships,
        win_pct=round((wins / games) * 100, 2),
        trades_completed=trades_completed,
        total_points_scored=round(points_for, 2),
        years_played=years_played,
        dynasty_power_rating=power,
    )


@router.get("/rivalries", response_model=RivalryList)
def get_rivalries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RivalryList:
    home_team = aliased(Team)
    away_team = aliased(Team)
    rows = (
        db.query(
            Matchup.home_score,
            Matchup.away_score,
            home_team.owner_user_id.label("home_user_id"),
            away_team.owner_user_id.label("away_user_id"),
            home_team.owner_name.label("home_owner_name"),
            away_team.owner_name.label("away_owner_name"),
        )
        .join(home_team, home_team.id == Matchup.home_team_id)
        .join(away_team, away_team.id == Matchup.away_team_id)
        .filter(or_(home_team.owner_user_id == current_user.id, away_team.owner_user_id == current_user.id))
        .all()
    )

    rivalry_map: dict[int, dict[str, float | int | str]] = defaultdict(
        lambda: {
            "wins": 0,
            "losses": 0,
            "points_for": 0.0,
            "points_against": 0.0,
            "matchups": 0,
            "name": "Rival",
        }
    )
    for row in rows:
        home_user_id = row.home_user_id
        away_user_id = row.away_user_id
        if not home_user_id or not away_user_id or home_user_id == away_user_id:
            continue
        home_score = float(row.home_score or 0.0)
        away_score = float(row.away_score or 0.0)

        if home_user_id == current_user.id:
            rival_id = away_user_id
            points_for = home_score
            points_against = away_score
            won = home_score > away_score
            rival_name = row.away_owner_name or f"User {away_user_id}"
        else:
            rival_id = home_user_id
            points_for = away_score
            points_against = home_score
            won = away_score > home_score
            rival_name = row.home_owner_name or f"User {home_user_id}"

        entry = rivalry_map[rival_id]
        entry["matchups"] += 1
        entry["points_for"] += points_for
        entry["points_against"] += points_against
        entry["name"] = str(rival_name)
        if won:
            entry["wins"] += 1
        else:
            entry["losses"] += 1

    output: list[RivalryRow] = []
    for rival_id, entry in rivalry_map.items():
        matchup_count = int(entry["matchups"])
        trash_talk_score = min(100, (int(entry["wins"]) * 12) + matchup_count * 4)
        output.append(
            RivalryRow(
                rival_user_id=rival_id,
                rival_name=str(entry["name"]),
                record_wins=int(entry["wins"]),
                record_losses=int(entry["losses"]),
                total_points_for=round(float(entry["points_for"]), 2),
                total_points_against=round(float(entry["points_against"]), 2),
                matchup_count=matchup_count,
                trash_talk_score=trash_talk_score,
            )
        )
    output.sort(key=lambda row: (row.matchup_count, row.trash_talk_score), reverse=True)
    return RivalryList(data=output, total=len(output))


@router.get("/users/leaderboard", response_model=UserAnalyticsList)
def get_user_analytics_leaderboard(
    limit: int = 100,
    db: Session = Depends(get_db),
) -> UserAnalyticsList:
    users = db.query(User).order_by(User.created_at.asc()).all()
    if not users:
        return UserAnalyticsList(data=[], total=0)
    user_stats = _build_user_matchup_stats(db)
    championships_map = _championships_by_user(db)
    rows: list[UserAnalyticsRow] = []
    for user in users:
        stats = user_stats.get(user.id, {})
        wins = int(stats.get("wins", 0))
        losses = int(stats.get("losses", 0))
        points_for = float(stats.get("points_for", 0.0))
        leagues_count = db.query(Team.league_id).filter(Team.owner_user_id == user.id).distinct().count()
        trades_completed = (
            db.query(NotificationLog)
            .filter(
                and_(
                    _notification_log_user_filter(user.id),
                    or_(NotificationLog.alert_type == "TRADE", NotificationLog.alert_type == "TRADE_ACCEPTED"),
                )
            )
            .count()
        )
        games = max(1, wins + losses)
        rows.append(
            UserAnalyticsRow(
                user_id=user.id,
                name=user.first_name,
                championships=championships_map.get(user.id, 0),
                win_pct=round((wins / games) * 100, 2),
                total_points=round(points_for, 2),
                trades_completed=trades_completed,
                dynasty_power_rating=_dynasty_power(
                    wins=wins,
                    losses=losses,
                    championships=championships_map.get(user.id, 0),
                    total_points=points_for,
                    league_count=leagues_count,
                    trades_completed=trades_completed,
                ),
            )
        )
    rows.sort(key=lambda row: row.dynasty_power_rating, reverse=True)
    return UserAnalyticsList(data=rows[:limit], total=min(len(rows), limit))


def _next_opponent_for_player(db: Session, player: Player, season: int, week: int) -> str | None:
    game = (
        db.query(Game)
        .filter(
            Game.season == season,
            Game.week == week,
            or_(Game.home_team == player.school, Game.away_team == player.school),
        )
        .first()
    )
    if not game:
        return None
    return game.away_team if game.home_team == player.school else game.home_team


def _compare_side(db: Session, player: Player, season: int, week: int) -> PlayerCompareSide:
    projection = (
        db.query(WeeklyProjection)
        .filter(
            WeeklyProjection.player_id == player.id,
            WeeklyProjection.season == season,
            WeeklyProjection.week == week,
        )
        .first()
    )
    fantasy_ppg = float(projection.fantasy_points or 0.0) if projection else 0.0
    usage_rate = 0.0
    red_zone_touches = 0.0
    if projection:
        if player.position.upper() == "QB":
            usage_rate = float(projection.pass_attempts or 0.0) + float(projection.rush_attempts or 0.0)
        else:
            usage_rate = float(projection.targets or 0.0) + float(projection.rush_attempts or 0.0)
        red_zone_touches = (
            float(projection.rush_tds or 0.0) * 2.4
            + float(projection.rec_tds or 0.0) * 2.1
            + float(projection.pass_tds or 0.0) * 0.8
        )

    opponent = _next_opponent_for_player(db, player, season, week)
    difficulty = "C"
    if opponent:
        defense = (
            db.query(DefenseRating)
            .filter(DefenseRating.team_name == opponent, DefenseRating.season == season, DefenseRating.week == week)
            .first()
        )
        cached = (
            db.query(DefenseVsPosition)
            .filter(
                DefenseVsPosition.team_name == opponent,
                DefenseVsPosition.season == season,
                DefenseVsPosition.week == week,
                DefenseVsPosition.position == player.position.upper(),
            )
            .first()
        )
        row = build_matchup_row(opponent, season, week, player.position.upper(), defense, cached)
        difficulty = row.get("grade", "C")

    return PlayerCompareSide(
        player_id=player.id,
        player_name=player.name,
        school=player.school,
        position=player.position,
        fantasy_ppg=round(fantasy_ppg, 2),
        usage_rate=round(usage_rate, 2),
        red_zone_touches=round(red_zone_touches, 2),
        projected_matchup_difficulty=difficulty,
    )


@router.post("/player-compare", response_model=PlayerCompareResponse)
def compare_players(
    payload: PlayerCompareRequest,
    db: Session = Depends(get_db),
) -> PlayerCompareResponse:
    player_a = db.query(Player).filter(Player.id == payload.player_a_id).first()
    player_b = db.query(Player).filter(Player.id == payload.player_b_id).first()
    if not player_a or not player_b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="player not found")
    return PlayerCompareResponse(
        player_a=_compare_side(db, player_a, payload.season, payload.week),
        player_b=_compare_side(db, player_b, payload.season, payload.week),
    )
