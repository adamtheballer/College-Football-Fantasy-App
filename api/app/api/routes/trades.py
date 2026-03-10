from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.db.session import get_db
from collegefootballfantasy_api.app.models.defense_rating import DefenseRating
from collegefootballfantasy_api.app.models.defense_vs_position import DefenseVsPosition
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.trade import TradeAnalyzeRequest, TradeAnalyzeResponse
from collegefootballfantasy_api.app.services.matchup_grades import build_matchup_row

router = APIRouter()

DEFAULT_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "FLEX": 1,
    "K": 1,
    "BE": 4,
    "IR": 1,
}

FLEX_DISTRIBUTION = {"RB": 0.45, "WR": 0.45, "TE": 0.10}
BENCH_DISTRIBUTION = {
    "QB": 0.10,
    "RB": 0.35,
    "WR": 0.35,
    "TE": 0.10,
    "K": 0.05,
    "FLEX": 0.05,
}

GRADE_MULTIPLIER = {
    "A+": 1.08,
    "A": 1.05,
    "B": 1.02,
    "C": 1.0,
    "D": 0.97,
    "F": 0.94,
}


def _normalize_roster_slots(roster_slots: dict[str, int] | None) -> dict[str, int]:
    slots = DEFAULT_ROSTER_SLOTS.copy()
    if roster_slots:
        for key, value in roster_slots.items():
            slots[key.upper()] = int(value)
    return slots


def _replacement_index(pos: str, league_size: int, roster_slots: dict[str, int]) -> int:
    starters = roster_slots.get(pos, 0) * league_size
    flex_slots = roster_slots.get("FLEX", 0) * league_size
    bench_slots = (roster_slots.get("BE", 0) + roster_slots.get("IR", 0)) * league_size
    flex_share = flex_slots * FLEX_DISTRIBUTION.get(pos, 0.0)
    bench_share = bench_slots * BENCH_DISTRIBUTION.get(pos, 0.0)
    return max(1, round(starters + flex_share + bench_share))


def _build_replacement_by_pos(
    db: Session, season: int, week: int, league_size: int, roster_slots: dict[str, int]
) -> dict[str, float]:
    rows = (
        db.query(WeeklyProjection, Player)
        .join(Player, WeeklyProjection.player_id == Player.id)
        .filter(WeeklyProjection.season == season, WeeklyProjection.week == week)
        .all()
    )
    points_by_pos: dict[str, list[float]] = {}
    for projection, player in rows:
        pos = player.position.upper()
        if pos not in {"QB", "RB", "WR", "TE", "K"}:
            continue
        points_by_pos.setdefault(pos, []).append(projection.fantasy_points or 0.0)

    replacement_by_pos: dict[str, float] = {}
    for pos, values in points_by_pos.items():
        values_sorted = sorted(values, reverse=True)
        index = _replacement_index(pos, league_size, roster_slots) - 1
        index = max(0, min(index, len(values_sorted) - 1))
        replacement_by_pos[pos] = values_sorted[index] if values_sorted else 0.0
    return replacement_by_pos


def _injury_multiplier(status: str | None) -> float:
    if not status:
        return 1.0
    status = status.upper()
    if status == "OUT":
        return 0.4
    if status == "DOUBTFUL":
        return 0.6
    if status == "QUESTIONABLE":
        return 0.8
    if status == "PROBABLE":
        return 0.95
    return 1.0


def _schedule_multiplier(
    db: Session, player: Player, season: int, week: int, weeks: int = 4
) -> float:
    games = (
        db.query(Game)
        .filter(Game.season == season, Game.week >= week)
        .filter(or_(Game.home_team == player.school, Game.away_team == player.school))
        .order_by(Game.week.asc())
        .limit(weeks)
        .all()
    )
    if not games:
        return 1.0

    multipliers: list[float] = []
    for game in games:
        opponent = game.away_team if game.home_team == player.school else game.home_team
        cached = (
            db.query(DefenseVsPosition)
            .filter(
                DefenseVsPosition.team_name == opponent,
                DefenseVsPosition.season == season,
                DefenseVsPosition.week == game.week,
                DefenseVsPosition.position == player.position.upper(),
            )
            .first()
        )
        defense = (
            db.query(DefenseRating)
            .filter(DefenseRating.team_name == opponent, DefenseRating.season == season, DefenseRating.week == game.week)
            .first()
        )
        row = build_matchup_row(opponent, season, game.week, player.position, defense, cached)
        multipliers.append(GRADE_MULTIPLIER.get(row["grade"], 1.0))
    return round(sum(multipliers) / len(multipliers), 3) if multipliers else 1.0


def _player_value(
    player: Player,
    projection: WeeklyProjection | None,
    replacement_by_pos: dict[str, float],
    injury_status: str | None,
    schedule_mult: float,
) -> float:
    points = projection.fantasy_points if projection else 0.0
    replacement = replacement_by_pos.get(player.position.upper(), 0.0)
    points_above = points - replacement
    scarcity_bonus = max(0.0, points_above) * 0.5
    injury_mult = _injury_multiplier(injury_status)
    value = (points + scarcity_bonus) * injury_mult * schedule_mult
    return round(value, 2)


@router.post("/analyze", response_model=TradeAnalyzeResponse)
def analyze_trade(payload: TradeAnalyzeRequest, db: Session = Depends(get_db)) -> TradeAnalyzeResponse:
    if not payload.receive_ids or not payload.give_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="receive_ids and give_ids required")

    players = db.query(Player).filter(Player.id.in_(payload.receive_ids + payload.give_ids)).all()
    player_by_id = {player.id: player for player in players}

    projections = (
        db.query(WeeklyProjection)
        .filter(WeeklyProjection.season == payload.season, WeeklyProjection.week == payload.week)
        .filter(WeeklyProjection.player_id.in_(payload.receive_ids + payload.give_ids))
        .all()
    )
    proj_by_id = {proj.player_id: proj for proj in projections}

    injuries = (
        db.query(Injury)
        .filter(Injury.season == payload.season, Injury.week == payload.week)
        .filter(Injury.player_id.in_(payload.receive_ids + payload.give_ids))
        .all()
    )
    injury_by_id = {inj.player_id: inj for inj in injuries}

    roster_slots = _normalize_roster_slots(payload.roster_slots)
    replacement_by_pos = _build_replacement_by_pos(
        db, payload.season, payload.week, payload.league_size, roster_slots
    )

    receive_value = 0.0
    for pid in payload.receive_ids:
        player = player_by_id.get(pid)
        if player:
            injury_status = injury_by_id.get(pid).status if injury_by_id.get(pid) else None
            schedule_mult = _schedule_multiplier(db, player, payload.season, payload.week)
            receive_value += _player_value(
                player,
                proj_by_id.get(pid),
                replacement_by_pos,
                injury_status,
                schedule_mult,
            )

    give_value = 0.0
    for pid in payload.give_ids:
        player = player_by_id.get(pid)
        if player:
            injury_status = injury_by_id.get(pid).status if injury_by_id.get(pid) else None
            schedule_mult = _schedule_multiplier(db, player, payload.season, payload.week)
            give_value += _player_value(
                player,
                proj_by_id.get(pid),
                replacement_by_pos,
                injury_status,
                schedule_mult,
            )

    delta = receive_value - give_value
    verdict = "Even"
    if give_value > 0:
        delta_pct = delta / give_value
        if delta_pct >= 0.08:
            verdict = "Strong Win"
        elif delta_pct >= 0.03:
            verdict = "Slight Win"
        elif delta_pct <= -0.08:
            verdict = "Strong Loss"
        elif delta_pct <= -0.03:
            verdict = "Slight Loss"

    return TradeAnalyzeResponse(
        receive_value=round(receive_value, 2),
        give_value=round(give_value, 2),
        delta=round(delta, 2),
        verdict=verdict,
    )
