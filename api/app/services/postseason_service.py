"""Deterministic championship-playoff lifecycle.

The regular-season standings table is the source of truth for qualification.
Postseason results never reseed a completed regular season: seeds are locked
from the final regular-season snapshot, while later standings snapshots remain
available for the full-season record.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

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
from collegefootballfantasy_api.app.models.team import Team


FINAL_MATCHUP_STATUSES = {"final", "stat_corrected"}
SUPPORTED_BRACKET_SIZES = {2, 4, 6, 8}


@dataclass(frozen=True)
class PostseasonLifecycleSummary:
    bracket_created: bool = False
    matchups_created: int = 0
    matchups_finalized: int = 0
    bracket_completed: bool = False


@dataclass(frozen=True)
class RankedTeam:
    team: Team
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    tiebreaker_explanation: str | None = None

    @property
    def win_percentage(self) -> float:
        games = self.wins + self.losses + self.ties
        return (self.wins + (0.5 * self.ties)) / games if games else 0.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_playoff_team_count(requested: int, team_count: int) -> int:
    eligible = min(max(team_count, 0), requested)
    valid = [size for size in SUPPORTED_BRACKET_SIZES if size <= eligible]
    return max(valid) if valid else 0


def get_or_create_postseason_settings(db: Session, league: League) -> LeaguePostseasonSettings:
    settings = (
        db.query(LeaguePostseasonSettings)
        .filter(
            LeaguePostseasonSettings.league_id == league.id,
            LeaguePostseasonSettings.season == league.season_year,
        )
        .one_or_none()
    )
    if settings:
        return settings

    league_settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).one_or_none()
    team_count = db.query(Team).filter(Team.league_id == league.id).count()
    requested = league_settings.playoff_teams if league_settings else 4
    playoff_team_count = _normalized_playoff_team_count(requested, team_count)
    settings = LeaguePostseasonSettings(
        league_id=league.id,
        season=league.season_year,
        regular_season_start_week=1,
        regular_season_end_week=10,
        playoff_start_week=11,
        championship_week=13,
        playoff_team_count=playoff_team_count,
        championship_bracket_size=playoff_team_count,
        # The beta ships one auditable championship bracket. Do not advertise
        # consolation or third-place rounds until their lifecycle is wired.
        third_place_game_enabled=False,
        losers_bracket_enabled=False,
    )
    db.add(settings)
    db.flush()
    return settings


def regular_season_end_week(db: Session, league: League) -> int:
    return get_or_create_postseason_settings(db, league).regular_season_end_week


def _latest_regular_standings(
    db: Session,
    league: League,
    settings: LeaguePostseasonSettings,
) -> list[RankedTeam]:
    rows = (
        db.query(Standing, Team)
        .join(Team, Team.id == Standing.team_id)
        .filter(
            Standing.league_id == league.id,
            Standing.season == league.season_year,
            Standing.week == settings.regular_season_end_week,
        )
        .all()
    )
    return [
        RankedTeam(
            team=team,
            wins=standing.wins,
            losses=standing.losses,
            ties=standing.ties,
            points_for=float(standing.points_for),
            points_against=float(standing.points_against),
        )
        for standing, team in rows
    ]


def _head_to_head_percentages(
    db: Session,
    league: League,
    settings: LeaguePostseasonSettings,
    group: list[RankedTeam],
) -> dict[int, float] | None:
    """Return a decisive complete mini-table, otherwise defer to PF/PA.

    Head-to-head is only used when every tied team has played every other tied
    team in the regular season. That prevents an unequal schedule from deciding
    a seed unfairly.
    """
    if len(group) < 2:
        return None
    team_ids = {entry.team.id for entry in group}
    records = {team_id: [0, 0, 0] for team_id in team_ids}
    pair_counts = {frozenset((left, right)): 0 for left in team_ids for right in team_ids if left < right}
    matchups = (
        db.query(Matchup)
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            Matchup.week >= settings.regular_season_start_week,
            Matchup.week <= settings.regular_season_end_week,
            Matchup.status.in_(FINAL_MATCHUP_STATUSES),
        )
        .all()
    )
    for matchup in matchups:
        if matchup.home_team_id not in team_ids or matchup.away_team_id not in team_ids:
            continue
        pair_counts[frozenset((matchup.home_team_id, matchup.away_team_id))] += 1
        home_score = float(matchup.home_score or 0.0)
        away_score = float(matchup.away_score or 0.0)
        if home_score > away_score:
            records[matchup.home_team_id][0] += 1
            records[matchup.away_team_id][1] += 1
        elif away_score > home_score:
            records[matchup.away_team_id][0] += 1
            records[matchup.home_team_id][1] += 1
        else:
            records[matchup.home_team_id][2] += 1
            records[matchup.away_team_id][2] += 1
    if not pair_counts or any(count == 0 for count in pair_counts.values()):
        return None
    percentages = {
        team_id: (wins + (0.5 * ties)) / (wins + losses + ties)
        for team_id, (wins, losses, ties) in records.items()
        if wins + losses + ties
    }
    return percentages if len(set(percentages.values())) > 1 else None


def rank_regular_season_teams(
    db: Session,
    league: League,
    settings: LeaguePostseasonSettings,
) -> list[RankedTeam]:
    """Rank using win percentage, complete head-to-head, PF, PA, then team id.

    The final team-id fallback is intentionally deterministic and recorded so a
    standings tie can never leave a playoff bracket blocked.
    """
    standings = _latest_regular_standings(db, league, settings)
    win_groups: dict[float, list[RankedTeam]] = {}
    for entry in standings:
        win_groups.setdefault(entry.win_percentage, []).append(entry)

    ranked: list[RankedTeam] = []
    for win_percentage in sorted(win_groups, reverse=True):
        group = win_groups[win_percentage]
        head_to_head = _head_to_head_percentages(db, league, settings, group)
        ordered = sorted(
            group,
            key=lambda entry: (
                -(head_to_head.get(entry.team.id, 0.0) if head_to_head else 0.0),
                -entry.points_for,
                entry.points_against,
                entry.team.id,
            ),
        )
        for index, entry in enumerate(ordered):
            explanation = None
            if len(group) > 1:
                if head_to_head and len({head_to_head[item.team.id] for item in group}) > 1:
                    explanation = "head_to_head"
                elif len({item.points_for for item in group}) > 1:
                    explanation = "points_for"
                elif len({item.points_against for item in group}) > 1:
                    explanation = "points_against"
                else:
                    explanation = "deterministic_team_id"
            ranked.append(
                RankedTeam(
                    team=entry.team,
                    wins=entry.wins,
                    losses=entry.losses,
                    ties=entry.ties,
                    points_for=entry.points_for,
                    points_against=entry.points_against,
                    tiebreaker_explanation=explanation,
                )
            )
    return ranked


def _all_regular_season_matchups_final(db: Session, league: League, settings: LeaguePostseasonSettings) -> bool:
    team_count = db.query(Team).filter(Team.league_id == league.id).count()
    if team_count < 2 or team_count % 2:
        return False

    matchups = (
        db.query(Matchup)
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            Matchup.week >= settings.regular_season_start_week,
            Matchup.week <= settings.regular_season_end_week,
        )
        .all()
    )
    expected_matchups_per_week = team_count // 2
    matchups_by_week: dict[int, list[Matchup]] = {}
    for matchup in matchups:
        matchups_by_week.setdefault(matchup.week, []).append(matchup)

    # A partial schedule must not seed a playoff bracket early.  Every regular
    # season week needs one finalized matchup per pair of teams.
    for week in range(settings.regular_season_start_week, settings.regular_season_end_week + 1):
        week_matchups = matchups_by_week.get(week, [])
        if len(week_matchups) != expected_matchups_per_week:
            return False
        if any((matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES for matchup in week_matchups):
            return False
    return True


def _round_plan(settings: LeaguePostseasonSettings) -> list[tuple[int, int, str]]:
    size = settings.playoff_team_count
    if size == 2:
        return [(1, settings.championship_week, "CHAMPIONSHIP")]
    if size == 4:
        return [(1, settings.playoff_start_week, "SEMIFINAL"), (2, settings.championship_week, "CHAMPIONSHIP")]
    if size == 6:
        return [
            (1, settings.playoff_start_week, "QUARTERFINAL"),
            (2, settings.playoff_start_week + 1, "SEMIFINAL"),
            (3, settings.championship_week, "CHAMPIONSHIP"),
        ]
    if size == 8:
        return [
            (1, settings.playoff_start_week, "QUARTERFINAL"),
            (2, settings.playoff_start_week + 1, "SEMIFINAL"),
            (3, settings.championship_week, "CHAMPIONSHIP"),
        ]
    raise ValueError("playoff_team_count must be one of 2, 4, 6, or 8")


def _initial_round_pairs(size: int) -> list[tuple[int, int]]:
    if size == 2:
        return [(1, 2)]
    if size == 4:
        return [(1, 4), (2, 3)]
    if size == 6:
        return [(3, 6), (4, 5)]
    if size == 8:
        return [(1, 8), (4, 5), (2, 7), (3, 6)]
    raise ValueError("unsupported playoff bracket size")


def _create_matchup(
    db: Session,
    bracket: PostseasonBracket,
    round_row: PostseasonRound,
    team_a: Team,
    team_b: Team,
    seed_by_team_id: dict[int, int],
    slot_number: int,
) -> PostseasonMatchup:
    fantasy_matchup = Matchup(
        league_id=bracket.league_id,
        season=bracket.season,
        week=round_row.week,
        home_team_id=team_a.id,
        away_team_id=team_b.id,
        status="projected",
        home_score=0.0,
        away_score=0.0,
    )
    db.add(fantasy_matchup)
    db.flush()
    record = PostseasonMatchup(
        bracket_id=bracket.id,
        round_id=round_row.id,
        fantasy_matchup_id=fantasy_matchup.id,
        slot_number=slot_number,
        team_a_id=team_a.id,
        team_b_id=team_b.id,
        team_a_seed=seed_by_team_id[team_a.id],
        team_b_seed=seed_by_team_id[team_b.id],
        advancement_rule="higher_score_then_higher_seed",
        status="SCHEDULED",
        metadata_json={"postseason": True, "round_type": round_row.round_type},
    )
    db.add(record)
    return record


def _create_bracket(db: Session, league: League, settings: LeaguePostseasonSettings) -> PostseasonBracket | None:
    ranked = rank_regular_season_teams(db, league, settings)
    size = _normalized_playoff_team_count(settings.playoff_team_count, len(ranked))
    if size != settings.playoff_team_count or size == 0:
        return None
    bracket = PostseasonBracket(
        league_id=league.id,
        season=league.season_year,
        bracket_type="CHAMPIONSHIP",
        status="ACTIVE",
        total_teams=size,
        total_rounds=len(_round_plan(settings)),
        generated_at=_now(),
    )
    db.add(bracket)
    db.flush()
    seed_by_team_id: dict[int, int] = {}
    team_by_seed: dict[int, Team] = {}
    for seed, entry in enumerate(ranked[:size], start=1):
        seed_by_team_id[entry.team.id] = seed
        team_by_seed[seed] = entry.team
        db.add(
            PostseasonEntry(
                bracket_id=bracket.id,
                team_id=entry.team.id,
                regular_season_rank=seed,
                bracket_seed=seed,
                qualification_status="QUALIFIED",
                tiebreaker_explanation=entry.tiebreaker_explanation,
                qualified_at=_now(),
                status="ACTIVE",
            )
        )
    db.flush()
    rounds: list[PostseasonRound] = []
    for round_number, week, round_type in _round_plan(settings):
        round_row = PostseasonRound(
            bracket_id=bracket.id,
            round_number=round_number,
            week=week,
            round_type=round_type,
            status="SCHEDULED",
        )
        db.add(round_row)
        rounds.append(round_row)
    db.flush()
    for slot_number, (seed_a, seed_b) in enumerate(_initial_round_pairs(size), start=1):
        _create_matchup(
            db,
            bracket,
            rounds[0],
            team_by_seed[seed_a],
            team_by_seed[seed_b],
            seed_by_team_id,
            slot_number,
        )
    settings.locked_at = _now()
    return bracket


def _seed_by_team(db: Session, bracket_id: int) -> dict[int, int]:
    return {
        entry.team_id: entry.bracket_seed
        for entry in db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == bracket_id).all()
    }


def _finalize_completed_postseason_matchups(db: Session, bracket: PostseasonBracket) -> int:
    finalized = 0
    for record, matchup in (
        db.query(PostseasonMatchup, Matchup)
        .join(Matchup, Matchup.id == PostseasonMatchup.fantasy_matchup_id)
        .filter(PostseasonMatchup.bracket_id == bracket.id, PostseasonMatchup.status != "FINAL")
        .all()
    ):
        if (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
            continue
        home_score = float(matchup.home_score or 0.0)
        away_score = float(matchup.away_score or 0.0)
        if home_score > away_score:
            winner, loser, tiebreaker = record.team_a_id, record.team_b_id, None
        elif away_score > home_score:
            winner, loser, tiebreaker = record.team_b_id, record.team_a_id, None
        elif (record.team_a_seed or 99_999) <= (record.team_b_seed or 99_999):
            winner, loser, tiebreaker = record.team_a_id, record.team_b_id, "higher_seed"
        else:
            winner, loser, tiebreaker = record.team_b_id, record.team_a_id, "higher_seed"
        record.advancing_team_id = winner
        record.eliminated_or_safe_team_id = loser
        record.tiebreaker_used = tiebreaker
        record.status = "FINAL"
        record.finalized_at = _now()
        finalized += 1
    if finalized:
        finalized_round_ids = {
            round_id
            for (round_id,) in db.query(PostseasonMatchup.round_id)
            .filter(PostseasonMatchup.bracket_id == bracket.id, PostseasonMatchup.status == "FINAL")
            .all()
        }
        for round_row in (
            db.query(PostseasonRound)
            .filter(PostseasonRound.bracket_id == bracket.id, PostseasonRound.id.in_(finalized_round_ids))
            .all()
        ):
            total = db.query(PostseasonMatchup).filter(PostseasonMatchup.round_id == round_row.id).count()
            final = (
                db.query(PostseasonMatchup)
                .filter(PostseasonMatchup.round_id == round_row.id, PostseasonMatchup.status == "FINAL")
                .count()
            )
            if total and total == final:
                round_row.status = "FINAL"
        db.flush()
    return finalized


def _create_ready_next_round(db: Session, bracket: PostseasonBracket) -> int:
    rounds = (
        db.query(PostseasonRound)
        .filter(PostseasonRound.bracket_id == bracket.id)
        .order_by(PostseasonRound.round_number.asc())
        .all()
    )
    seed_by_team_id = _seed_by_team(db, bracket.id)
    created = 0
    for index in range(1, len(rounds)):
        prior_round = rounds[index - 1]
        next_round = rounds[index]
        if db.query(PostseasonMatchup).filter(PostseasonMatchup.round_id == next_round.id).count():
            continue
        prior_matchups = (
            db.query(PostseasonMatchup)
            .filter(PostseasonMatchup.round_id == prior_round.id)
            .order_by(PostseasonMatchup.slot_number.asc())
            .all()
        )
        if not prior_matchups or any(item.status != "FINAL" for item in prior_matchups):
            continue
        advancing_ids = [item.advancing_team_id for item in prior_matchups if item.advancing_team_id]
        # Six-team brackets award first-round byes to seeds one and two.
        if bracket.total_teams == 6 and prior_round.round_number == 1:
            advancing_ids.extend(
                team_id for team_id, seed in seed_by_team_id.items() if seed in {1, 2}
            )
        advancing_ids = sorted(set(advancing_ids), key=lambda team_id: seed_by_team_id[team_id])
        if len(advancing_ids) < 2 or len(advancing_ids) % 2:
            continue
        teams = {team.id: team for team in db.query(Team).filter(Team.id.in_(advancing_ids)).all()}
        for slot_number in range(len(advancing_ids) // 2):
            first = advancing_ids[slot_number]
            second = advancing_ids[-(slot_number + 1)]
            _create_matchup(db, bracket, next_round, teams[first], teams[second], seed_by_team_id, slot_number + 1)
            created += 1
    return created


def _finalize_bracket_if_complete(db: Session, bracket: PostseasonBracket) -> bool:
    championship_round = (
        db.query(PostseasonRound)
        .filter(PostseasonRound.bracket_id == bracket.id, PostseasonRound.round_type == "CHAMPIONSHIP")
        .one()
    )
    championship = (
        db.query(PostseasonMatchup)
        .filter(PostseasonMatchup.round_id == championship_round.id)
        .one_or_none()
    )
    if not championship or championship.status != "FINAL":
        return False
    bracket.status = "COMPLETED"
    bracket.finalized_at = _now()
    seeds = _seed_by_team(db, bracket.id)
    entries = {entry.team_id: entry for entry in db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == bracket.id).all()}
    ordered = [championship.advancing_team_id, championship.eliminated_or_safe_team_id]
    eliminated = [
        matchup.eliminated_or_safe_team_id
        for matchup in db.query(PostseasonMatchup)
        .filter(PostseasonMatchup.bracket_id == bracket.id, PostseasonMatchup.status == "FINAL")
        .all()
        if matchup.eliminated_or_safe_team_id not in ordered
    ]
    ordered.extend(sorted(set(eliminated), key=lambda team_id: seeds[team_id]))
    league = db.get(League, bracket.league_id)
    settings = get_or_create_postseason_settings(db, league)
    regular_ranked = rank_regular_season_teams(db, league, settings)
    regular_rank_by_team_id = {entry.team.id: index for index, entry in enumerate(regular_ranked, start=1)}
    regular_record_by_team_id = {entry.team.id: entry for entry in regular_ranked}

    # Preserve a complete season table, including teams that did not qualify.
    # This is the final auditable record for wins, losses, PF and PA used when
    # a postseason tiebreaker or historical standings view needs to be traced.
    already_placed = set(ordered)
    ordered.extend(entry.team.id for entry in regular_ranked if entry.team.id not in already_placed)
    db.query(PostseasonFinalStanding).filter(
        PostseasonFinalStanding.league_id == bracket.league_id,
        PostseasonFinalStanding.season == bracket.season,
    ).delete(synchronize_session=False)
    for place, team_id in enumerate(ordered, start=1):
        entry = entries.get(team_id)
        regular = regular_record_by_team_id[team_id]
        if entry:
            entry.final_place = place
            entry.status = "CHAMPION" if place == 1 else "RUNNER_UP" if place == 2 else "ELIMINATED"
        if place == 1:
            postseason_result = "CHAMPION"
        elif place == 2:
            postseason_result = "RUNNER_UP"
        elif entry:
            postseason_result = "ELIMINATED"
        else:
            postseason_result = "NOT_QUALIFIED"
        db.add(
            PostseasonFinalStanding(
                league_id=bracket.league_id,
                season=bracket.season,
                team_id=team_id,
                final_place=place,
                regular_season_rank=regular_rank_by_team_id[team_id],
                playoff_seed=entry.bracket_seed if entry else None,
                postseason_result=postseason_result,
                wins=regular.wins,
                losses=regular.losses,
                ties=regular.ties,
                points_for=regular.points_for,
                finalized_at=_now(),
            )
        )
    return True


def progress_postseason(db: Session, league: League, season: int, week: int) -> PostseasonLifecycleSummary:
    """Create, advance, and finalize a championship bracket exactly once."""
    if season != league.season_year:
        return PostseasonLifecycleSummary()
    settings = get_or_create_postseason_settings(db, league)
    if week < settings.regular_season_end_week:
        return PostseasonLifecycleSummary()
    bracket = (
        db.query(PostseasonBracket)
        .filter(
            PostseasonBracket.league_id == league.id,
            PostseasonBracket.season == season,
            PostseasonBracket.bracket_type == "CHAMPIONSHIP",
        )
        .one_or_none()
    )
    created = False
    if not bracket:
        if not _all_regular_season_matchups_final(db, league, settings):
            return PostseasonLifecycleSummary()
        bracket = _create_bracket(db, league, settings)
        if bracket is None:
            return PostseasonLifecycleSummary()
        created = True
    if bracket.status == "COMPLETED":
        return PostseasonLifecycleSummary(bracket_created=created)
    finalized = _finalize_completed_postseason_matchups(db, bracket)
    matchups_created = _create_ready_next_round(db, bracket)
    completed = _finalize_bracket_if_complete(db, bracket)
    db.flush()
    return PostseasonLifecycleSummary(
        bracket_created=created,
        matchups_created=matchups_created,
        matchups_finalized=finalized,
        bracket_completed=completed,
    )
