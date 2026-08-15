"""Server-authoritative playoff seeding and fixed-bracket lifecycle.

Regular-season standings and canonical matchup scoring remain the source of
truth.  This module only consumes those certified records, persists a locked
result, and advances an already-persisted bracket.  It deliberately has no
client-supplied seeds, scores, or winners.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from secrets import token_hex
from typing import Any, Callable, Iterable

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.postseason import (
    LeaguePostseasonSettings,
    PostseasonBracket,
    PostseasonEntry,
    PostseasonFinalStanding,
    PostseasonMatchup,
    PostseasonRound,
)
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.scoring_admin_audit import ScoringAdminAudit
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.services.scoring_service import recalculate_standings_for_week


CERTIFIED_MATCHUP_STATUSES = {"final", "stat_corrected"}
SUPPORTED_PLAYOFF_TEAM_COUNTS = {4, 6}
BRACKET_TYPE_CHAMPIONSHIP = "championship"


class PostseasonError(ValueError):
    """A safe lifecycle conflict or invalid authoritative state."""


@dataclass
class SeedCandidate:
    team: Team
    wins: int
    losses: int
    ties: int
    points_for: Decimal
    points_against: Decimal
    weekly_scores: tuple[Decimal, ...]
    lot: str
    trace: list[dict[str, Any]] = field(default_factory=list)

    @property
    def games_played(self) -> int:
        return self.wins + self.losses + self.ties

    @property
    def winning_percentage(self) -> Fraction | None:
        if self.games_played == 0:
            return None
        return Fraction((self.wins * 2) + self.ties, self.games_played * 2)

    def record_payload(self) -> dict[str, Any]:
        percentage = self.winning_percentage
        return {
            "wins": self.wins,
            "losses": self.losses,
            "ties": self.ties,
            "games_played": self.games_played,
            "winning_percentage": float(percentage) if percentage is not None else None,
            "points_for": float(self.points_for),
            "points_against": float(self.points_against),
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_decimal(value: float | int | Decimal | None) -> Decimal:
    return Decimal(str(value if value is not None else 0))


def _configured_postseason_settings(db: Session, league: League, *, lock: bool = False) -> LeaguePostseasonSettings:
    query = db.query(LeaguePostseasonSettings).filter(
        LeaguePostseasonSettings.league_id == league.id,
        LeaguePostseasonSettings.season == league.season_year,
    )
    if lock:
        query = query.with_for_update()
    row = query.one_or_none()
    if row is not None:
        return row

    league_settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).one_or_none()
    playoff_team_count = int(league_settings.playoff_teams if league_settings else 4)
    row = LeaguePostseasonSettings(
        league_id=league.id,
        season=league.season_year,
        regular_season_start_week=1,
        regular_season_end_week=10,
        playoff_start_week=11,
        championship_week=13,
        playoff_team_count=playoff_team_count,
        championship_bracket_size=playoff_team_count,
        reseeding_enabled=False,
        third_place_game_enabled=False,
        losers_bracket_enabled=False,
    )
    db.add(row)
    db.flush()
    return row


def ensure_postseason_tiebreak_lots(db: Session, league_id: int) -> None:
    """Give every team one persistent lot before it is ever used in seeding."""
    teams = db.query(Team).filter(Team.league_id == league_id).with_for_update().order_by(Team.id).all()
    used = {team.postseason_tiebreak_lot for team in teams if team.postseason_tiebreak_lot}
    for team in teams:
        if team.postseason_tiebreak_lot:
            continue
        lot = token_hex(24)
        while lot in used:
            lot = token_hex(24)
        team.postseason_tiebreak_lot = lot
        used.add(lot)
    db.flush()


def _regular_matchups(db: Session, league: League, settings: LeaguePostseasonSettings) -> list[Matchup]:
    return (
        db.query(Matchup)
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            Matchup.week >= settings.regular_season_start_week,
            Matchup.week <= settings.regular_season_end_week,
        )
        .order_by(Matchup.week, Matchup.id)
        .all()
    )


def _assert_seeding_ready(db: Session, league: League, settings: LeaguePostseasonSettings) -> list[Matchup]:
    matchups = _regular_matchups(db, league, settings)
    if not matchups:
        raise PostseasonError("regular-season schedule is not available")
    unfinalized = [matchup.week for matchup in matchups if (matchup.status or "").lower() not in CERTIFIED_MATCHUP_STATUSES]
    if unfinalized:
        weeks = ", ".join(str(week) for week in sorted(set(unfinalized)))
        raise PostseasonError(f"regular-season scoring is not certified for week(s): {weeks}")
    scheduled_team_ids = {matchup.home_team_id for matchup in matchups} | {matchup.away_team_id for matchup in matchups}
    league_team_ids = {
        team_id
        for (team_id,) in db.query(Team.id).filter(Team.league_id == league.id).all()
    }
    missing = sorted(league_team_ids - scheduled_team_ids)
    if missing:
        raise PostseasonError("regular-season schedule is incomplete for one or more league teams")
    return matchups


def _weekly_scores(db: Session, league: League, settings: LeaguePostseasonSettings, team_ids: set[int]) -> dict[int, tuple[Decimal, ...]]:
    # A team-week value is eligible only when that team's regular-season
    # matchup has itself reached canonical certification.
    final_weeks_by_team: dict[int, set[int]] = defaultdict(set)
    for matchup in _regular_matchups(db, league, settings):
        if (matchup.status or "").lower() in CERTIFIED_MATCHUP_STATUSES:
            final_weeks_by_team[matchup.home_team_id].add(matchup.week)
            final_weeks_by_team[matchup.away_team_id].add(matchup.week)
    rows = (
        db.query(TeamWeekScore)
        .filter(
            TeamWeekScore.league_id == league.id,
            TeamWeekScore.season == league.season_year,
            TeamWeekScore.team_id.in_(team_ids or {0}),
            TeamWeekScore.week >= settings.regular_season_start_week,
            TeamWeekScore.week <= settings.regular_season_end_week,
        )
        .all()
    )
    values: dict[int, list[Decimal]] = {team_id: [] for team_id in team_ids}
    for row in rows:
        if row.week in final_weeks_by_team.get(row.team_id, set()):
            values[row.team_id].append(_canonical_decimal(row.total_points))
    return {team_id: tuple(sorted(scores, reverse=True)) for team_id, scores in values.items()}


def _candidate_set(db: Session, league: League, settings: LeaguePostseasonSettings) -> list[SeedCandidate]:
    # Use the existing canonical standings service; do not maintain a second
    # record engine just for postseason.
    recalculate_standings_for_week(db, league.id, league.season_year, settings.regular_season_end_week)
    teams = db.query(Team).filter(Team.league_id == league.id).order_by(Team.id).all()
    if settings.playoff_team_count not in SUPPORTED_PLAYOFF_TEAM_COUNTS:
        raise PostseasonError("alpha postseason supports 4 or 6 playoff teams")
    if settings.playoff_team_count >= len(teams):
        raise PostseasonError("playoff team count must be smaller than league team count")
    ensure_postseason_tiebreak_lots(db, league.id)
    standings = {
        row.team_id: row
        for row in db.query(Standing)
        .filter(
            Standing.league_id == league.id,
            Standing.season == league.season_year,
            Standing.week == settings.regular_season_end_week,
        )
        .all()
    }
    weekly_scores = _weekly_scores(db, league, settings, {team.id for team in teams})
    return [
        SeedCandidate(
            team=team,
            wins=int(standings.get(team.id).wins if team.id in standings else 0),
            losses=int(standings.get(team.id).losses if team.id in standings else 0),
            ties=int(standings.get(team.id).ties if team.id in standings else 0),
            points_for=_canonical_decimal(standings.get(team.id).points_for if team.id in standings else 0),
            points_against=_canonical_decimal(standings.get(team.id).points_against if team.id in standings else 0),
            weekly_scores=weekly_scores.get(team.id, ()),
            lot=team.postseason_tiebreak_lot or "",
        )
        for team in teams
    ]


def _head_to_head_values(
    db: Session,
    league: League,
    settings: LeaguePostseasonSettings,
    candidates: list[SeedCandidate],
) -> dict[int, Fraction] | None:
    """Return a fair mini-table or ``None`` when schedule symmetry is absent.

    For three or more teams, every pair must have played the same positive
    number of certified regular-season games.  This excludes incomplete or
    asymmetric mini-tables instead of inventing a comparison from a schedule
    advantage.
    """
    team_ids = {candidate.team.id for candidate in candidates}
    if len(team_ids) < 2:
        return None
    rows = [
        matchup
        for matchup in _regular_matchups(db, league, settings)
        if (matchup.status or "").lower() in CERTIFIED_MATCHUP_STATUSES
        and matchup.home_team_id in team_ids
        and matchup.away_team_id in team_ids
    ]
    pair_counts: dict[tuple[int, int], int] = defaultdict(int)
    records: dict[int, list[int]] = {team_id: [0, 0, 0] for team_id in team_ids}
    for matchup in rows:
        pair = tuple(sorted((matchup.home_team_id, matchup.away_team_id)))
        pair_counts[pair] += 1
        home_score = _canonical_decimal(matchup.home_score)
        away_score = _canonical_decimal(matchup.away_score)
        if home_score > away_score:
            records[matchup.home_team_id][0] += 1
            records[matchup.away_team_id][1] += 1
        elif away_score > home_score:
            records[matchup.away_team_id][0] += 1
            records[matchup.home_team_id][1] += 1
        else:
            records[matchup.home_team_id][2] += 1
            records[matchup.away_team_id][2] += 1
    expected_pairs = [tuple(sorted((left, right))) for index, left in enumerate(sorted(team_ids)) for right in sorted(team_ids)[index + 1 :]]
    counts = [pair_counts.get(pair, 0) for pair in expected_pairs]
    if not counts or any(count <= 0 for count in counts) or len(set(counts)) != 1:
        return None
    values: dict[int, Fraction] = {}
    for team_id, (wins, losses, ties) in records.items():
        games = wins + losses + ties
        if games == 0:
            return None
        values[team_id] = Fraction((wins * 2) + ties, games * 2)
    return values


def _partition(values: dict[int, Any], candidates: list[SeedCandidate], *, reverse: bool = True) -> list[list[SeedCandidate]]:
    grouped: dict[Any, list[SeedCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[values[candidate.team.id]].append(candidate)
    return [grouped[value] for value in sorted(grouped, reverse=reverse)]


def _criterion_values(
    db: Session,
    league: League,
    settings: LeaguePostseasonSettings,
    candidates: list[SeedCandidate],
    criterion: str,
) -> dict[int, Any] | None:
    if criterion == "winning_percentage":
        # Zero-game teams are deterministic but unseeded in ordinary use; the
        # readiness rule prevents this for a finished regular season.
        return {candidate.team.id: candidate.winning_percentage or Fraction(-1, 1) for candidate in candidates}
    if criterion == "points_for":
        return {candidate.team.id: candidate.points_for for candidate in candidates}
    if criterion == "head_to_head":
        return _head_to_head_values(db, league, settings, candidates)
    if criterion == "best_weekly_score":
        return {candidate.team.id: candidate.weekly_scores for candidate in candidates}
    if criterion == "tiebreak_lot":
        return {candidate.team.id: candidate.lot for candidate in candidates}
    raise AssertionError(f"unknown tiebreak criterion: {criterion}")


_TIEBREAK_ORDER = ("winning_percentage", "points_for", "head_to_head", "best_weekly_score", "tiebreak_lot")


def _resolve_tied_group(
    db: Session,
    league: League,
    settings: LeaguePostseasonSettings,
    candidates: list[SeedCandidate],
    *,
    group_ids: tuple[int, ...] | None = None,
) -> list[SeedCandidate]:
    if len(candidates) <= 1:
        return candidates
    original_ids = group_ids or tuple(sorted(candidate.team.id for candidate in candidates))
    for criterion in _TIEBREAK_ORDER:
        values = _criterion_values(db, league, settings, candidates, criterion)
        if values is None:
            for candidate in candidates:
                candidate.trace.append({"criterion": criterion, "status": "skipped_asymmetric"})
            continue
        # Lot is ascending: it is an opaque order, not a sporting statistic.
        partitions = _partition(values, candidates, reverse=criterion != "tiebreak_lot")
        if len(partitions) == 1:
            continue
        resolved: list[SeedCandidate] = []
        for partition in partitions:
            if len(partition) == 1:
                candidate = partition[0]
                candidate.trace.append(
                    {
                        "criterion": criterion,
                        "tiebreak_group_team_ids": list(original_ids),
                        "result": "higher" if criterion != "tiebreak_lot" else "lot_order",
                        "comparison_value": str(values[candidate.team.id]),
                    }
                )
                resolved.append(candidate)
            else:
                # A partial separation restarts at win percentage for the
                # remaining subset as required by the canonical policy.
                resolved.extend(_resolve_tied_group(db, league, settings, partition))
        return resolved
    raise PostseasonError("tiebreak lots must be unique within a league")


def calculate_seeding(db: Session, league: League) -> list[SeedCandidate]:
    settings = _configured_postseason_settings(db, league)
    _assert_seeding_ready(db, league, settings)
    candidates = _candidate_set(db, league, settings)
    return _resolve_tied_group(db, league, settings, candidates)


def _seed_explanation(candidate: SeedCandidate, seed: int, ranked: list[SeedCandidate]) -> dict[str, Any]:
    return {
        "seed": seed,
        "team_id": candidate.team.id,
        "team_name": candidate.team.name,
        "record": candidate.record_payload(),
        "qualified": seed <= len(ranked),
        "resolved_by": candidate.trace[-1]["criterion"] if candidate.trace else "winning_percentage",
        "tiebreak_group_team_ids": candidate.trace[-1].get("tiebreak_group_team_ids", []) if candidate.trace else [],
        "trace": candidate.trace,
    }


def preview_postseason_seeding(db: Session, league: League) -> dict[str, Any]:
    settings = _configured_postseason_settings(db, league)
    ranked = calculate_seeding(db, league)
    return {
        "league_id": league.id,
        "season": league.season_year,
        "state": "SEEDING_LOCKED" if settings.locked_at else "SEEDING_PENDING",
        "playoff_team_count": settings.playoff_team_count,
        "seeding_locked_at": settings.locked_at,
        "tiebreak_order": list(_TIEBREAK_ORDER),
        "entries": [
            _seed_explanation(candidate, index, ranked[: settings.playoff_team_count])
            for index, candidate in enumerate(ranked, start=1)
        ],
    }


def _matchup_sources(*, team_a: dict[str, Any], team_b: dict[str, Any]) -> dict[str, Any]:
    return {"sources": {"team_a": team_a, "team_b": team_b}}


def _create_round(db: Session, bracket: PostseasonBracket, number: int, week: int, round_type: str) -> PostseasonRound:
    row = PostseasonRound(bracket_id=bracket.id, round_number=number, week=week, round_type=round_type, status="SCHEDULED")
    db.add(row)
    db.flush()
    return row


def _create_postseason_matchup(
    db: Session,
    *,
    bracket: PostseasonBracket,
    round_row: PostseasonRound,
    slot_number: int,
    team_a_id: int | None,
    team_b_id: int | None,
    team_a_seed: int | None,
    team_b_seed: int | None,
    metadata: dict[str, Any],
) -> PostseasonMatchup:
    row = PostseasonMatchup(
        bracket_id=bracket.id,
        round_id=round_row.id,
        slot_number=slot_number,
        team_a_id=team_a_id,
        team_b_id=team_b_id,
        team_a_seed=team_a_seed,
        team_b_seed=team_b_seed,
        advancement_rule="higher_original_seed_on_tie",
        status="SCHEDULED" if team_a_id and team_b_id else "PENDING",
        metadata_json=metadata,
    )
    db.add(row)
    db.flush()
    _ensure_scored_matchup(db, row, round_row.week, bracket)
    return row


def _ensure_scored_matchup(db: Session, postseason_matchup: PostseasonMatchup, week: int, bracket: PostseasonBracket) -> None:
    if postseason_matchup.fantasy_matchup_id or not postseason_matchup.team_a_id or not postseason_matchup.team_b_id:
        return
    matchup = Matchup(
        league_id=bracket.league_id,
        season=bracket.season,
        week=week,
        home_team_id=postseason_matchup.team_a_id,
        away_team_id=postseason_matchup.team_b_id,
        status="scheduled",
        home_score=0.0,
        away_score=0.0,
    )
    db.add(matchup)
    db.flush()
    postseason_matchup.fantasy_matchup_id = matchup.id
    postseason_matchup.status = "SCHEDULED"


def _entry_by_seed(db: Session, bracket_id: int) -> dict[int, PostseasonEntry]:
    return {
        entry.bracket_seed: entry
        for entry in db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == bracket_id).all()
    }


def generate_locked_bracket(db: Session, league: League) -> PostseasonBracket:
    settings = _configured_postseason_settings(db, league, lock=True)
    if settings.locked_at is None:
        raise PostseasonError("seeding must be locked before generating a bracket")
    bracket = (
        db.query(PostseasonBracket)
        .filter(
            PostseasonBracket.league_id == league.id,
            PostseasonBracket.season == league.season_year,
            PostseasonBracket.bracket_type == BRACKET_TYPE_CHAMPIONSHIP,
        )
        .with_for_update()
        .one()
    )
    existing = db.query(PostseasonRound).filter(PostseasonRound.bracket_id == bracket.id).count()
    if existing:
        return bracket
    seeds = _entry_by_seed(db, bracket.id)
    if set(seeds) != set(range(1, settings.playoff_team_count + 1)):
        raise PostseasonError("locked seeding entries are incomplete")
    bracket.status = "PLAYOFFS_ACTIVE"
    if settings.playoff_team_count == 4:
        semis = _create_round(db, bracket, 1, settings.playoff_start_week, "SEMIFINALS")
        championship = _create_round(db, bracket, 2, settings.championship_week, "CHAMPIONSHIP")
        first = _create_postseason_matchup(
            db, bracket=bracket, round_row=semis, slot_number=1,
            team_a_id=seeds[1].team_id, team_b_id=seeds[4].team_id, team_a_seed=1, team_b_seed=4,
            metadata=_matchup_sources(team_a={"seed": 1}, team_b={"seed": 4}),
        )
        second = _create_postseason_matchup(
            db, bracket=bracket, round_row=semis, slot_number=2,
            team_a_id=seeds[2].team_id, team_b_id=seeds[3].team_id, team_a_seed=2, team_b_seed=3,
            metadata=_matchup_sources(team_a={"seed": 2}, team_b={"seed": 3}),
        )
        _create_postseason_matchup(
            db, bracket=bracket, round_row=championship, slot_number=1,
            team_a_id=None, team_b_id=None, team_a_seed=None, team_b_seed=None,
            metadata=_matchup_sources(
                team_a={"winner_of": first.id}, team_b={"winner_of": second.id}
            ),
        )
    else:
        opening = _create_round(db, bracket, 1, settings.playoff_start_week, "OPENING_ROUND")
        semis = _create_round(db, bracket, 2, settings.playoff_start_week + 1, "SEMIFINALS")
        championship = _create_round(db, bracket, 3, settings.championship_week, "CHAMPIONSHIP")
        three_six = _create_postseason_matchup(
            db, bracket=bracket, round_row=opening, slot_number=1,
            team_a_id=seeds[3].team_id, team_b_id=seeds[6].team_id, team_a_seed=3, team_b_seed=6,
            metadata=_matchup_sources(team_a={"seed": 3}, team_b={"seed": 6}),
        )
        four_five = _create_postseason_matchup(
            db, bracket=bracket, round_row=opening, slot_number=2,
            team_a_id=seeds[4].team_id, team_b_id=seeds[5].team_id, team_a_seed=4, team_b_seed=5,
            metadata=_matchup_sources(team_a={"seed": 4}, team_b={"seed": 5}),
        )
        semi_one = _create_postseason_matchup(
            db, bracket=bracket, round_row=semis, slot_number=1,
            team_a_id=seeds[1].team_id, team_b_id=None, team_a_seed=1, team_b_seed=None,
            metadata=_matchup_sources(team_a={"seed": 1, "bye": True}, team_b={"winner_of": four_five.id}),
        )
        semi_two = _create_postseason_matchup(
            db, bracket=bracket, round_row=semis, slot_number=2,
            team_a_id=seeds[2].team_id, team_b_id=None, team_a_seed=2, team_b_seed=None,
            metadata=_matchup_sources(team_a={"seed": 2, "bye": True}, team_b={"winner_of": three_six.id}),
        )
        _create_postseason_matchup(
            db, bracket=bracket, round_row=championship, slot_number=1,
            team_a_id=None, team_b_id=None, team_a_seed=None, team_b_seed=None,
            metadata=_matchup_sources(team_a={"winner_of": semi_one.id}, team_b={"winner_of": semi_two.id}),
        )
    db.flush()
    return bracket


def lock_postseason_seeding(db: Session, league: League) -> PostseasonBracket:
    """Atomically lock authoritative seeds and generate one fixed bracket."""
    db.query(League).filter(League.id == league.id).with_for_update().one()
    settings = _configured_postseason_settings(db, league, lock=True)
    existing = (
        db.query(PostseasonBracket)
        .filter(
            PostseasonBracket.league_id == league.id,
            PostseasonBracket.season == league.season_year,
            PostseasonBracket.bracket_type == BRACKET_TYPE_CHAMPIONSHIP,
        )
        .one_or_none()
    )
    if settings.locked_at and existing:
        return existing
    _assert_seeding_ready(db, league, settings)
    ranked = _candidate_set(db, league, settings)
    ranked = _resolve_tied_group(db, league, settings, ranked)
    if existing is None:
        existing = PostseasonBracket(
            league_id=league.id,
            season=league.season_year,
            bracket_type=BRACKET_TYPE_CHAMPIONSHIP,
            status="SEEDING_LOCKED",
            total_teams=settings.playoff_team_count,
            total_rounds=2 if settings.playoff_team_count == 4 else 3,
            generated_at=_now(),
        )
        db.add(existing)
        db.flush()
    for seed, candidate in enumerate(ranked[: settings.playoff_team_count], start=1):
        explanation = _seed_explanation(candidate, seed, ranked[: settings.playoff_team_count])
        db.add(
            PostseasonEntry(
                bracket_id=existing.id,
                team_id=candidate.team.id,
                regular_season_rank=seed,
                bracket_seed=seed,
                qualification_status="QUALIFIED",
                tiebreaker_explanation=explanation["resolved_by"],
                seeding_trace_json=explanation,
                qualified_at=_now(),
                status="ACTIVE",
            )
        )
    settings.locked_at = _now()
    db.flush()
    return generate_locked_bracket(db, league)


def refresh_locked_postseason_after_regular_correction(
    db: Session,
    league: League,
    *,
    scoring_week: int | None = None,
) -> bool:
    """Regenerate a locked bracket only before any playoff game has started.

    A stat correction may change a regular-season qualifier. The source data is
    recalculated by the normal scoring flow, then this function atomically
    replaces only unstarted, generated playoff artifacts. Once a playoff game
    is live or certified, the fixed bracket is immutable.
    """
    settings = _configured_postseason_settings(db, league, lock=True)
    if scoring_week is not None and scoring_week > settings.regular_season_end_week:
        return False
    if settings.locked_at is None:
        return False
    bracket = (
        db.query(PostseasonBracket)
        .filter(
            PostseasonBracket.league_id == league.id,
            PostseasonBracket.season == league.season_year,
            PostseasonBracket.bracket_type == BRACKET_TYPE_CHAMPIONSHIP,
        )
        .with_for_update()
        .one_or_none()
    )
    if bracket is None or bracket.status == "POSTSEASON_COMPLETE":
        return False
    matchup_rows = db.query(PostseasonMatchup).filter(PostseasonMatchup.bracket_id == bracket.id).all()
    fantasy_ids = [row.fantasy_matchup_id for row in matchup_rows if row.fantasy_matchup_id]
    fantasy_rows = db.query(Matchup).filter(Matchup.id.in_(fantasy_ids or [-1])).all()
    if any((row.status or "").lower() not in {"scheduled", "pending"} for row in fantasy_rows):
        return False

    before_entries = _entry_by_seed(db, bracket.id)
    for row in matchup_rows:
        db.delete(row)
    db.flush()
    for row in fantasy_rows:
        db.delete(row)
    for round_row in db.query(PostseasonRound).filter(PostseasonRound.bracket_id == bracket.id).all():
        db.delete(round_row)
    for entry in before_entries.values():
        db.delete(entry)
    db.flush()

    old_seeds = {str(seed): entry.team_id for seed, entry in before_entries.items()}
    settings.locked_at = None
    bracket.status = "SEEDING_REBUILDING"
    db.flush()
    rebuilt = lock_postseason_seeding(db, league)
    db.add(
        ScoringAdminAudit(
            action="postseason_seeding_rebuilt_after_stat_correction",
            actor_user_id=None,
            league_id=league.id,
            season=league.season_year,
            week=settings.regular_season_end_week,
            affected_league_ids=[league.id],
            reason="Regular-season certified scoring changed before the first playoff game began.",
            before_state={"seeds": old_seeds},
            after_state={"bracket_id": rebuilt.id, "seeds": {str(seed): entry.team_id for seed, entry in _entry_by_seed(db, rebuilt.id).items()}},
        )
    )
    db.flush()
    return True


def _source_team(db: Session, bracket_id: int, source: dict[str, Any]) -> tuple[int | None, int | None]:
    if "seed" in source:
        entry = (
            db.query(PostseasonEntry)
            .filter(PostseasonEntry.bracket_id == bracket_id, PostseasonEntry.bracket_seed == int(source["seed"]))
            .one()
        )
        return entry.team_id, entry.bracket_seed
    predecessor = db.get(PostseasonMatchup, int(source["winner_of"]))
    if predecessor is None or predecessor.bracket_id != bracket_id or predecessor.advancing_team_id is None:
        return None, None
    entry = (
        db.query(PostseasonEntry)
        .filter(PostseasonEntry.bracket_id == bracket_id, PostseasonEntry.team_id == predecessor.advancing_team_id)
        .one()
    )
    return predecessor.advancing_team_id, entry.bracket_seed


def _populate_ready_matchups(db: Session, bracket: PostseasonBracket) -> None:
    rounds = {round_row.id: round_row for round_row in db.query(PostseasonRound).filter(PostseasonRound.bracket_id == bracket.id).all()}
    rows = db.query(PostseasonMatchup).filter(PostseasonMatchup.bracket_id == bracket.id).with_for_update().all()
    for row in rows:
        sources = (row.metadata_json or {}).get("sources", {})
        team_a_id, team_a_seed = _source_team(db, bracket.id, sources.get("team_a", {}))
        team_b_id, team_b_seed = _source_team(db, bracket.id, sources.get("team_b", {}))
        if team_a_id and row.team_a_id != team_a_id:
            row.team_a_id, row.team_a_seed = team_a_id, team_a_seed
        if team_b_id and row.team_b_id != team_b_id:
            row.team_b_id, row.team_b_seed = team_b_id, team_b_seed
        _ensure_scored_matchup(db, row, rounds[row.round_id].week, bracket)


def _finalize_championship(db: Session, bracket: PostseasonBracket, matchup: PostseasonMatchup) -> None:
    if matchup.advancing_team_id is None or matchup.eliminated_or_safe_team_id is None:
        return
    bracket.status = "POSTSEASON_COMPLETE"
    bracket.finalized_at = _now()
    entries = db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == bracket.id).all()
    entry_by_team = {entry.team_id: entry for entry in entries}
    # The championship establishes places one and two. Teams eliminated in an
    # earlier round receive stable, unique placements by their exit round then
    # original seed. This records a complete final playoff table without
    # fabricating extra placement games.
    placements: list[tuple[int, int, str]] = [
        (1, matchup.advancing_team_id, "CHAMPION"),
        (2, matchup.eliminated_or_safe_team_id, "RUNNER_UP"),
    ]
    remaining = [
        entry
        for entry in entries
        if entry.team_id not in {matchup.advancing_team_id, matchup.eliminated_or_safe_team_id}
    ]
    remaining.sort(key=lambda entry: (-(entry.eliminated_or_escaped_round or 0), entry.bracket_seed))
    placements.extend(
        (place, entry.team_id, f"ELIMINATED_{entry.eliminated_or_escaped_round or 'UNKNOWN'}")
        for place, entry in enumerate(remaining, start=3)
    )
    for final_place, team_id, result in placements:
        row = (
            db.query(PostseasonFinalStanding)
            .filter(PostseasonFinalStanding.league_id == bracket.league_id, PostseasonFinalStanding.season == bracket.season, PostseasonFinalStanding.team_id == team_id)
            .one_or_none()
        )
        entry = entry_by_team[team_id]
        if row is None:
            row = PostseasonFinalStanding(
                league_id=bracket.league_id,
                season=bracket.season,
                team_id=team_id,
                final_place=final_place,
                regular_season_rank=entry.regular_season_rank,
                playoff_seed=entry.bracket_seed,
                postseason_result=result,
                wins=0,
                losses=0,
                ties=0,
                points_for=0.0,
                finalized_at=_now(),
            )
            db.add(row)
        else:
            row.final_place = final_place
            row.postseason_result = result
            row.finalized_at = _now()
        entry.final_place = final_place
        entry.status = result


def finalize_certified_postseason_matchups(db: Session, league: League) -> int:
    """Advance only certified playoff games; repeat calls are idempotent."""
    bracket = (
        db.query(PostseasonBracket)
        .filter(
            PostseasonBracket.league_id == league.id,
            PostseasonBracket.season == league.season_year,
            PostseasonBracket.bracket_type == BRACKET_TYPE_CHAMPIONSHIP,
        )
        .with_for_update()
        .one_or_none()
    )
    if bracket is None or bracket.status == "POSTSEASON_COMPLETE":
        return 0
    _populate_ready_matchups(db, bracket)
    rounds = {row.id: row for row in db.query(PostseasonRound).filter(PostseasonRound.bracket_id == bracket.id).all()}
    finalized = 0
    for row in (
        db.query(PostseasonMatchup)
        .filter(PostseasonMatchup.bracket_id == bracket.id, PostseasonMatchup.status == "SCHEDULED")
        .with_for_update()
        .all()
    ):
        matchup = db.get(Matchup, row.fantasy_matchup_id) if row.fantasy_matchup_id else None
        if matchup is None or (matchup.status or "").lower() not in CERTIFIED_MATCHUP_STATUSES:
            continue
        if row.advancing_team_id is not None:
            continue
        home_score = _canonical_decimal(matchup.home_score)
        away_score = _canonical_decimal(matchup.away_score)
        if home_score > away_score:
            winner, loser, tie_break = row.team_a_id, row.team_b_id, None
        elif away_score > home_score:
            winner, loser, tie_break = row.team_b_id, row.team_a_id, None
        elif (row.team_a_seed or 10**9) <= (row.team_b_seed or 10**9):
            winner, loser, tie_break = row.team_a_id, row.team_b_id, "higher_original_playoff_seed"
        else:
            winner, loser, tie_break = row.team_b_id, row.team_a_id, "higher_original_playoff_seed"
        row.advancing_team_id = winner
        row.eliminated_or_safe_team_id = loser
        row.tiebreaker_used = tie_break
        row.status = "FINAL"
        row.finalized_at = _now()
        eliminated = (
            db.query(PostseasonEntry)
            .filter(PostseasonEntry.bracket_id == bracket.id, PostseasonEntry.team_id == loser)
            .one_or_none()
        )
        if eliminated is not None:
            eliminated.status = "ELIMINATED"
            eliminated.eliminated_or_escaped_round = rounds[row.round_id].round_number
        finalized += 1
        if rounds[row.round_id].round_type == "CHAMPIONSHIP":
            _finalize_championship(db, bracket, row)
    if finalized:
        _populate_ready_matchups(db, bracket)
        db.flush()
    return finalized


def postseason_bracket_payload(db: Session, league: League) -> dict[str, Any] | None:
    bracket = (
        db.query(PostseasonBracket)
        .filter(
            PostseasonBracket.league_id == league.id,
            PostseasonBracket.season == league.season_year,
            PostseasonBracket.bracket_type == BRACKET_TYPE_CHAMPIONSHIP,
        )
        .one_or_none()
    )
    if bracket is None:
        return None
    entries = _entry_by_seed(db, bracket.id)
    rounds = {row.id: row for row in db.query(PostseasonRound).filter(PostseasonRound.bracket_id == bracket.id).all()}
    teams = {team.id: team.name for team in db.query(Team).filter(Team.league_id == league.id).all()}
    rows = (
        db.query(PostseasonMatchup)
        .filter(PostseasonMatchup.bracket_id == bracket.id)
        .order_by(PostseasonMatchup.round_id, PostseasonMatchup.slot_number)
        .all()
    )
    return {
        "league_id": league.id,
        "season": league.season_year,
        "status": bracket.status,
        "generated_at": bracket.generated_at,
        "finalized_at": bracket.finalized_at,
        "seeding_locked_at": _configured_postseason_settings(db, league).locked_at,
        "entries": [
            {
                "team_id": entry.team_id,
                "team_name": teams.get(entry.team_id, "Unknown team"),
                "seed": entry.bracket_seed,
                "regular_season_rank": entry.regular_season_rank,
                "status": entry.status,
                "explanation": entry.seeding_trace_json,
            }
            for _seed, entry in sorted(entries.items())
        ],
        "rounds": [
            {
                "round_number": rounds[row.round_id].round_number,
                "round_type": rounds[row.round_id].round_type,
                "week": rounds[row.round_id].week,
                "slot_number": row.slot_number,
                "status": row.status,
                "team_a": {"team_id": row.team_a_id, "team_name": teams.get(row.team_a_id) if row.team_a_id else None, "seed": row.team_a_seed},
                "team_b": {"team_id": row.team_b_id, "team_name": teams.get(row.team_b_id) if row.team_b_id else None, "seed": row.team_b_seed},
                "advancing_team_id": row.advancing_team_id,
                "tiebreaker_used": row.tiebreaker_used,
                "fantasy_matchup_id": row.fantasy_matchup_id,
                "metadata": row.metadata_json,
            }
            for row in rows
        ],
    }
