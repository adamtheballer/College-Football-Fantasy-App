"""Canonical fixed-bracket postseason service.

The postseason is routing metadata over ordinary ``Matchup`` rows.  Scoring,
lineup locks, live projections, and matchup finality remain owned by the
existing services.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable

from sqlalchemy import func
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
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.postseason_topology import (
    FIXED_BRACKET_FORMAT_VERSION,
    HIGHER_SEED_TIEBREAKER,
    SUPPORTED_PLAYOFF_TEAM_COUNTS,
    TopologyNode,
    build_bracket_topology,
    format_summary,
    required_rounds,
)
from collegefootballfantasy_api.app.services.notification_service import queue_notification_event
from collegefootballfantasy_api.app.services.season_calendar import calendar_for_season


FINAL_MATCHUP_STATUSES = frozenset({"final", "completed", "stat_corrected"})
STARTED_MATCHUP_STATUSES = frozenset({"live", "in_progress", *FINAL_MATCHUP_STATUSES})
POSTSEASON_STATUSES = frozenset({"PLANNED", "SEEDING_PENDING", "LOCKED", "ACTIVE", "FINALIZING", "COMPLETED", "REVIEW_REQUIRED"})
@dataclass(frozen=True)
class RankedTeam:
    team: Team
    wins: int
    losses: int
    ties: int
    points_for: float
    points_against: float
    rank: int
    tiebreaker_explanation: str | None
    draw_key: str | None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def validate_playoff_team_count(*, playoff_teams: int, max_teams: int) -> int:
    if playoff_teams not in SUPPORTED_PLAYOFF_TEAM_COUNTS:
        raise ValueError("playoff team count must be one of 2, 4, 6, or 8")
    if playoff_teams > max_teams:
        raise ValueError("playoff team count cannot exceed league max teams")
    return playoff_teams


def approved_fantasy_season_end_week(db: Session, season: int) -> int:
    """Compatibility read of the latest certified broad slate.

    ``db`` remains in this public function signature so existing callers do
    not accidentally substitute their imported schedule rows. It is never
    read: only the sealed release artifact may set postseason timing.
    """

    del db
    # Both three-round formats exercise the longest currently supported
    # window, which identifies the final certified championship slate.
    return calendar_for_season(season, 8).championship_week


def postseason_calendar(db: Session, league: League, playoff_teams: int) -> dict[str, int | str]:
    validate_playoff_team_count(playoff_teams=playoff_teams, max_teams=league.max_teams)
    del db
    calendar = calendar_for_season(league.season_year, playoff_teams)
    return {
        "regular_season_start_week": calendar.regular_season_start_week,
        "regular_season_end_week": calendar.regular_season_end_week,
        "playoff_start_week": calendar.playoff_start_week,
        "championship_week": calendar.championship_week,
        "rounds": calendar.max_rounds,
        "season_end_week": calendar.championship_week,
        "calendar_policy_version": calendar.calendar_policy_version,
        "calendar_source_identity": calendar.source_identity,
        "calendar_source_revision": calendar.source_revision,
        "calendar_source_sha256": calendar.source_sha256,
        "calendar_source_format_version": calendar.source_format_version,
    }


def get_or_create_postseason_settings(db: Session, league: League) -> LeaguePostseasonSettings:
    settings_row = db.query(LeaguePostseasonSettings).filter(
        LeaguePostseasonSettings.league_id == league.id,
        LeaguePostseasonSettings.season == league.season_year,
    ).one_or_none()
    if settings_row is None:
        league_settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).one_or_none()
        playoff_teams = validate_playoff_team_count(
            playoff_teams=int((league_settings.playoff_teams if league_settings else 4) or 4),
            max_teams=league.max_teams,
        )
        calendar = postseason_calendar(db, league, playoff_teams)
        settings_row = LeaguePostseasonSettings(
            league_id=league.id,
            season=league.season_year,
            playoff_team_count=playoff_teams,
            championship_bracket_size=playoff_teams,
            reseeding_enabled=False,
            regular_season_start_week=calendar["regular_season_start_week"],
            regular_season_end_week=calendar["regular_season_end_week"],
            playoff_start_week=calendar["playoff_start_week"],
            championship_week=calendar["championship_week"],
            calendar_policy_version=calendar["calendar_policy_version"],
            calendar_source_identity=calendar["calendar_source_identity"],
            calendar_source_revision=calendar["calendar_source_revision"],
            calendar_source_sha256=calendar["calendar_source_sha256"],
            calendar_source_format_version=calendar["calendar_source_format_version"],
        )
        db.add(settings_row)
        db.flush()
    return settings_row


def refresh_postseason_settings_calendar(
    db: Session,
    league: League,
    *,
    playoff_teams: int,
) -> LeaguePostseasonSettings:
    """Replace a planned calendar only before any league competition starts.

    This is deliberately the one regeneration path used by the commissioner
    settings mutation. Existing and started leagues retain their stored source
    provenance and are handled by the dry-run audit rather than being rewritten.
    """

    calendar = postseason_calendar(db, league, playoff_teams)
    settings_row = db.query(LeaguePostseasonSettings).filter(
        LeaguePostseasonSettings.league_id == league.id,
        LeaguePostseasonSettings.season == league.season_year,
    ).one_or_none()
    if settings_row is None:
        return get_or_create_postseason_settings(db, league)
    settings_row.playoff_team_count = playoff_teams
    settings_row.championship_bracket_size = playoff_teams
    settings_row.regular_season_start_week = calendar["regular_season_start_week"]
    settings_row.regular_season_end_week = calendar["regular_season_end_week"]
    settings_row.playoff_start_week = calendar["playoff_start_week"]
    settings_row.championship_week = calendar["championship_week"]
    settings_row.calendar_policy_version = calendar["calendar_policy_version"]
    settings_row.calendar_source_identity = calendar["calendar_source_identity"]
    settings_row.calendar_source_revision = calendar["calendar_source_revision"]
    settings_row.calendar_source_sha256 = calendar["calendar_source_sha256"]
    settings_row.calendar_source_format_version = calendar["calendar_source_format_version"]
    db.add(settings_row)
    db.flush()
    return settings_row


def _regular_final_matchups(db: Session, league: League, through_week: int) -> list[Matchup]:
    return db.query(Matchup).filter(
        Matchup.league_id == league.id,
        Matchup.season == league.season_year,
        Matchup.week <= through_week,
    ).all()


def regular_season_is_complete(db: Session, league: League, regular_season_end_week: int) -> bool:
    teams = db.query(Team.id).filter(Team.league_id == league.id).all()
    if len(teams) < 2:
        return False
    expected = (len(teams) // 2) * regular_season_end_week
    matchups = _regular_final_matchups(db, league, regular_season_end_week)
    return len(matchups) == expected and all((row.status or "").lower() in FINAL_MATCHUP_STATUSES for row in matchups)


def _standing_rows(db: Session, league: League, through_week: int) -> dict[int, dict[str, float]]:
    latest_week = db.query(func.max(Standing.week)).filter(
        Standing.league_id == league.id,
        Standing.season == league.season_year,
        Standing.week <= through_week,
    ).scalar()
    if latest_week is not None:
        return {
            row.team_id: {
                "wins": float(row.wins), "losses": float(row.losses), "ties": float(row.ties),
                "points_for": float(row.points_for), "points_against": float(row.points_against),
            }
            for row in db.query(Standing).filter(
                Standing.league_id == league.id, Standing.season == league.season_year, Standing.week == latest_week
            ).all()
        }
    values: dict[int, dict[str, float]] = defaultdict(lambda: {"wins": 0.0, "losses": 0.0, "ties": 0.0, "points_for": 0.0, "points_against": 0.0})
    for matchup in _regular_final_matchups(db, league, through_week):
        if (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
            continue
        home, away = values[matchup.home_team_id], values[matchup.away_team_id]
        home_score, away_score = float(matchup.home_score or 0), float(matchup.away_score or 0)
        home["points_for"] += home_score; home["points_against"] += away_score
        away["points_for"] += away_score; away["points_against"] += home_score
        if home_score > away_score: home["wins"] += 1; away["losses"] += 1
        elif away_score > home_score: away["wins"] += 1; home["losses"] += 1
        else: home["ties"] += 1; away["ties"] += 1
    return values


def _win_pct(row: dict[str, float]) -> float:
    games = row["wins"] + row["losses"] + row["ties"]
    return (row["wins"] + 0.5 * row["ties"]) / games if games else 0.0


def _head_to_head_score(matchups: Iterable[Matchup], team_id: int, group_ids: set[int]) -> float | None:
    if len(group_ids) < 2:
        return None
    wins = losses = ties = games = 0
    for matchup in matchups:
        if {matchup.home_team_id, matchup.away_team_id}.issubset(group_ids):
            if team_id not in {matchup.home_team_id, matchup.away_team_id} or (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
                continue
            mine = float(matchup.home_score or 0) if matchup.home_team_id == team_id else float(matchup.away_score or 0)
            theirs = float(matchup.away_score or 0) if matchup.home_team_id == team_id else float(matchup.home_score or 0)
            games += 1
            if mine > theirs: wins += 1
            elif mine < theirs: losses += 1
            else: ties += 1
    # H2H is safe only when every tied team faced every other tied team.
    return (wins + 0.5 * ties) / games if games == len(group_ids) - 1 else None


def rank_regular_season(db: Session, league: League, regular_season_end_week: int) -> list[RankedTeam]:
    """Single deterministic standings ranker for workspace and postseason seeding."""
    teams = db.query(Team).filter(Team.league_id == league.id).order_by(Team.id).all()
    records = _standing_rows(db, league, regular_season_end_week)
    regular_matchups = _regular_final_matchups(db, league, regular_season_end_week)
    preliminary = sorted(teams, key=lambda team: (-_win_pct(records.get(team.id, defaultdict(float))), -records.get(team.id, defaultdict(float))["points_for"]))
    ranked: list[RankedTeam] = []
    position = 1
    cursor = 0
    while cursor < len(preliminary):
        row = records.get(preliminary[cursor].id, defaultdict(float))
        base = (_win_pct(row), row["points_for"])
        group: list[Team] = []
        while cursor < len(preliminary):
            candidate = preliminary[cursor]
            candidate_row = records.get(candidate.id, defaultdict(float))
            if (_win_pct(candidate_row), candidate_row["points_for"]) != base:
                break
            group.append(candidate); cursor += 1
        group_ids = {team.id for team in group}
        h2h = {team.id: _head_to_head_score(regular_matchups, team.id, group_ids) for team in group}
        h2h_usable = len(group) > 1 and all(value is not None for value in h2h.values()) and len(set(h2h.values())) > 1
        ordered_group = sorted(
            group,
            key=lambda team: (
                -(h2h[team.id] or 0) if h2h_usable else 0,
                records.get(team.id, defaultdict(float))["points_against"],
                sha256(f"postseason-draw:{league.id}:{league.season_year}:{team.id}".encode()).hexdigest(),
            ),
        )
        for team in ordered_group:
            item = records.get(team.id, defaultdict(float))
            used_draw = len(ordered_group) > 1 and not h2h_usable and len({records.get(t.id, defaultdict(float))["points_against"] for t in ordered_group}) == 1
            explanation = "head-to-head" if h2h_usable else ("lower points against" if len(ordered_group) > 1 else None)
            if used_draw: explanation = "persisted deterministic draw"
            ranked.append(RankedTeam(
                team=team, wins=int(item["wins"]), losses=int(item["losses"]), ties=int(item["ties"]),
                points_for=float(item["points_for"]), points_against=float(item["points_against"]), rank=position,
                tiebreaker_explanation=explanation,
                draw_key=sha256(f"postseason-draw:{league.id}:{league.season_year}:{team.id}".encode()).hexdigest() if used_draw else None,
            ))
            position += 1
    return ranked


def _node_key(node: PostseasonMatchup) -> str:
    return str((node.metadata_json or {}).get("node_key") or "")


def _source_team_id(source: dict, entries_by_seed: dict[int, PostseasonEntry], nodes_by_key: dict[str, PostseasonMatchup]) -> int | None:
    kind, value = source["kind"], source["value"]
    if kind == "seed":
        entry = entries_by_seed.get(int(value)); return entry.team_id if entry else None
    node = nodes_by_key.get(str(value))
    if node is None:
        return None
    return node.winner_team_id if kind == "winner" else node.loser_team_id


def _team_seed(entries_by_team: dict[int, PostseasonEntry], team_id: int | None) -> int | None:
    entry = entries_by_team.get(team_id or -1)
    return entry.bracket_seed if entry else None


def _queue_team_notification(
    db: Session, *, league_id: int, team_id: int, event_type: str, event_key: str, title: str, body: str, payload: dict
) -> None:
    team = db.get(Team, team_id)
    if team is None or team.owner_user_id is None:
        return
    queue_notification_event(
        db, league_id=league_id, user_id=team.owner_user_id, event_type=event_type,
        event_key=event_key, title=title, body=body, payload=payload,
    )


def _ensure_rounds_and_nodes(db: Session, bracket: PostseasonBracket) -> dict[str, PostseasonMatchup]:
    topology = build_bracket_topology(bracket.total_teams)
    rounds: dict[int, PostseasonRound] = {row.round_number: row for row in db.query(PostseasonRound).filter(PostseasonRound.bracket_id == bracket.id).all()}
    for number in range(1, bracket.max_rounds + 1):
        if number not in rounds:
            round_row = PostseasonRound(bracket_id=bracket.id, round_number=number, week=bracket.playoff_start_week + number - 1, round_type="PLAYOFF", status="SCHEDULED")
            db.add(round_row); db.flush(); rounds[number] = round_row
    nodes = {_node_key(row): row for row in db.query(PostseasonMatchup).filter(PostseasonMatchup.bracket_id == bracket.id).all()}
    for spec in topology:
        if spec.key in nodes:
            continue
        row = PostseasonMatchup(
            bracket_id=bracket.id, round_id=rounds[spec.round_number].id, slot_number=spec.slot_number,
            matchup_type=spec.matchup_type, bracket_path=spec.bracket_path, advancement_rule=HIGHER_SEED_TIEBREAKER,
            metadata_json={"node_key": spec.key, "team_a_source": {"kind": spec.team_a.kind, "value": spec.team_a.value}, "team_b_source": {"kind": spec.team_b.kind, "value": spec.team_b.value}},
        )
        db.add(row); db.flush(); nodes[spec.key] = row
    for spec in topology:
        target = nodes[spec.key]
        for slot, source in (("A", spec.team_a), ("B", spec.team_b)):
            if source.kind == "seed":
                continue
            prior = nodes[str(source.value)]
            if source.kind == "winner":
                prior.next_winner_matchup_id, prior.next_winner_slot = target.id, slot
            else:
                prior.next_loser_matchup_id, prior.next_loser_slot = target.id, slot
    db.flush()
    return nodes


def _clear_pre_kickoff_bracket_materialization(db: Session, bracket: PostseasonBracket) -> None:
    """Clear only unstarted generated games before a permitted seed rebuild.

    A stat correction can change the regular-season seed snapshot before any
    playoff game has started.  The linked canonical Matchup rows are safe to
    discard only in that narrow state; any started/final row instead freezes
    the bracket and must go through review.
    """

    nodes = db.query(PostseasonMatchup).filter(PostseasonMatchup.bracket_id == bracket.id).all()
    linked_ids = [node.fantasy_matchup_id for node in nodes if node.fantasy_matchup_id]
    linked = {
        matchup.id: matchup
        for matchup in db.query(Matchup).filter(Matchup.id.in_(linked_ids)).all()
    } if linked_ids else {}
    started = [
        matchup.id
        for matchup in linked.values()
        if (matchup.status or "").lower() in STARTED_MATCHUP_STATUSES
    ]
    if started:
        bracket.status = "REVIEW_REQUIRED"
        bracket.review_reason = "seed correction arrived after postseason kickoff"
        bracket.review_metadata_json = {"affected_matchup_ids": started}
        raise ValueError("cannot rebuild postseason seeds after playoff kickoff")

    for matchup in linked.values():
        db.delete(matchup)
    for node in nodes:
        node.fantasy_matchup_id = None
        node.team_a_id = None
        node.team_b_id = None
        node.team_a_seed = None
        node.team_b_seed = None
        node.winner_team_id = None
        node.loser_team_id = None
        node.advancing_team_id = None
        node.eliminated_or_safe_team_id = None
        node.tiebreaker_used = None
        node.finalized_at = None
        node.status = "SCHEDULED"
    db.flush()


def lock_postseason_seeds(db: Session, league: League, *, now: datetime | None = None) -> PostseasonBracket:
    now = now or utcnow()
    plan = get_or_create_postseason_settings(db, league)
    if not regular_season_is_complete(db, league, plan.regular_season_end_week):
        bracket = db.query(PostseasonBracket).filter(PostseasonBracket.league_id == league.id, PostseasonBracket.season == league.season_year).one_or_none()
        if bracket:
            bracket.status = "SEEDING_PENDING"
        raise ValueError("regular season is not final through the configured end week")
    bracket = db.query(PostseasonBracket).filter(PostseasonBracket.league_id == league.id, PostseasonBracket.season == league.season_year).with_for_update().one_or_none()
    if bracket is None:
        bracket = PostseasonBracket(
            league_id=league.id, season=league.season_year, bracket_type="CHAMPIONSHIP", status="LOCKED",
            total_teams=plan.playoff_team_count, total_rounds=plan.championship_week - plan.playoff_start_week + 1,
            regular_season_start_week=plan.regular_season_start_week, regular_season_end_week=plan.regular_season_end_week,
            playoff_start_week=plan.playoff_start_week, championship_week=plan.championship_week,
            max_rounds=required_rounds(plan.playoff_team_count),
            calendar_policy_version=plan.calendar_policy_version,
            calendar_source_identity=plan.calendar_source_identity,
            calendar_source_revision=plan.calendar_source_revision,
            calendar_source_sha256=plan.calendar_source_sha256,
            calendar_source_format_version=plan.calendar_source_format_version,
            format_version=FIXED_BRACKET_FORMAT_VERSION, tiebreaker_policy=HIGHER_SEED_TIEBREAKER,
            generated_at=now, seeds_locked_at=now,
        )
        db.add(bracket); db.flush()
    if bracket.first_kickoff_at is not None:
        return bracket
    ranked = rank_regular_season(db, league, plan.regular_season_end_week)
    existing = {row.team_id: row for row in db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == bracket.id).all()}
    wanted = ranked[:bracket.total_teams]
    existing_seed_map = {row.team_id: row.bracket_seed for row in existing.values()}
    wanted_seed_map = {item.team.id: item.rank for item in wanted}
    if existing and existing_seed_map != wanted_seed_map:
        _clear_pre_kickoff_bracket_materialization(db, bracket)
        db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == bracket.id).delete(synchronize_session=False)
        existing = {}
    for item in wanted:
        entry = existing.get(item.team.id) or PostseasonEntry(bracket_id=bracket.id, team_id=item.team.id)
        entry.regular_season_rank, entry.bracket_seed = item.rank, item.rank
        entry.qualification_status, entry.tiebreaker_explanation, entry.tiebreak_draw_key = "LOCKED", item.tiebreaker_explanation, item.draw_key
        entry.qualified_at, entry.status = now, "ACTIVE"
        db.add(entry)
    plan.locked_at = now
    bracket.status, bracket.seeds_locked_at = "LOCKED", now
    _ensure_rounds_and_nodes(db, bracket)
    materialize_ready_postseason_matchups(db, bracket)
    for entry in db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == bracket.id).all():
        _queue_team_notification(
            db, league_id=league.id, team_id=entry.team_id, event_type="POSTSEASON_SEEDS_LOCKED",
            event_key=f"postseason:seeded:{bracket.id}:{entry.team_id}", title="Playoffs are set",
            body=f"You are the #{entry.bracket_seed} seed in {league.name}.", payload={"bracket_id": bracket.id, "seed": entry.bracket_seed},
        )
    return bracket


def materialize_ready_postseason_matchups(db: Session, bracket: PostseasonBracket) -> int:
    entries = db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == bracket.id).all()
    entries_by_seed, entries_by_team = ({entry.bracket_seed: entry for entry in entries}, {entry.team_id: entry for entry in entries})
    nodes = {_node_key(row): row for row in db.query(PostseasonMatchup).filter(PostseasonMatchup.bracket_id == bracket.id).all()}
    rounds = {row.id: row for row in db.query(PostseasonRound).filter(PostseasonRound.bracket_id == bracket.id).all()}
    created = 0
    for node in nodes.values():
        metadata = node.metadata_json or {}
        team_a = _source_team_id(metadata["team_a_source"], entries_by_seed, nodes)
        team_b = _source_team_id(metadata["team_b_source"], entries_by_seed, nodes)
        if team_a is not None: node.team_a_id, node.team_a_seed = team_a, _team_seed(entries_by_team, team_a)
        if team_b is not None: node.team_b_id, node.team_b_seed = team_b, _team_seed(entries_by_team, team_b)
        if node.fantasy_matchup_id is not None or not team_a or not team_b:
            continue
        # The higher seed is home.  A pre-existing canonical row is accepted
        # only when it has the exact same participants and reserved week.
        home, away = (team_a, team_b) if (node.team_a_seed or 999) <= (node.team_b_seed or 999) else (team_b, team_a)
        round_row = rounds[node.round_id]
        matchup = db.query(Matchup).filter(
            Matchup.league_id == bracket.league_id, Matchup.season == bracket.season,
            Matchup.week == round_row.week, Matchup.home_team_id == home, Matchup.away_team_id == away,
        ).one_or_none()
        if matchup is None:
            matchup = Matchup(league_id=bracket.league_id, season=bracket.season, week=round_row.week, home_team_id=home, away_team_id=away, status="projected", home_score=0.0, away_score=0.0)
            db.add(matchup); db.flush(); created += 1
        node.fantasy_matchup_id, node.status = matchup.id, matchup.status.upper()
        for participant_id in (team_a, team_b):
            _queue_team_notification(
                db, league_id=bracket.league_id, team_id=participant_id, event_type="POSTSEASON_MATCHUP_SET",
                event_key=f"postseason:matchup:{node.id}:{participant_id}", title="Playoff matchup set",
                body="Your next playoff matchup is ready.", payload={"postseason_matchup_id": node.id, "matchup_id": matchup.id},
            )
    db.flush()
    return created


def refresh_postseason_activity(db: Session, bracket: PostseasonBracket, *, now: datetime | None = None) -> bool:
    """Promote a locked bracket only when a linked canonical game actually starts."""

    if bracket.first_kickoff_at is not None:
        return False
    # The scoring worker may have just changed a Matchup status in this same
    # transaction. Flush before querying so activation never lags one cycle.
    db.flush()
    now = now or utcnow()
    linked_ids = [
        value
        for (value,) in db.query(PostseasonMatchup.fantasy_matchup_id)
        .filter(PostseasonMatchup.bracket_id == bracket.id, PostseasonMatchup.fantasy_matchup_id.is_not(None))
        .all()
    ]
    if not linked_ids:
        return False
    started = db.query(Matchup.id).filter(
        Matchup.id.in_(linked_ids),
        func.lower(Matchup.status).in_(STARTED_MATCHUP_STATUSES),
    ).first()
    if not started:
        return False
    bracket.first_kickoff_at = now
    bracket.status = "ACTIVE"
    db.flush()
    return True


def _write_participant(node: PostseasonMatchup, slot: str, team_id: int, seed_number: int | None) -> None:
    if slot == "A": node.team_a_id, node.team_a_seed = team_id, seed_number
    else: node.team_b_id, node.team_b_seed = team_id, seed_number


def resolve_postseason_matchup(db: Session, node: PostseasonMatchup, *, now: datetime | None = None) -> bool:
    now = now or utcnow()
    if node.fantasy_matchup_id is None:
        return False
    matchup = db.get(Matchup, node.fantasy_matchup_id)
    if matchup is None or (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
        return False
    if node.team_a_id is None or node.team_b_id is None:
        raise ValueError("materialized postseason matchup is missing a participant")
    # Scores remain canonical on Matchup.  Team A can be either home or away,
    # so derive both sides from the same ordering predicate.
    team_a_is_home = matchup.home_team_id == node.team_a_id
    a_score = float(matchup.home_score if team_a_is_home else matchup.away_score)
    b_score = float(matchup.away_score if team_a_is_home else matchup.home_score)
    if a_score > b_score: winner, loser, tie = node.team_a_id, node.team_b_id, None
    elif b_score > a_score: winner, loser, tie = node.team_b_id, node.team_a_id, None
    else:
        winner, loser = (node.team_a_id, node.team_b_id) if (node.team_a_seed or 999) < (node.team_b_seed or 999) else (node.team_b_id, node.team_a_id)
        tie = HIGHER_SEED_TIEBREAKER
    if node.winner_team_id is not None and node.winner_team_id != winner:
        return reconcile_postseason_correction(db, node, winner_team_id=winner, loser_team_id=loser, now=now)
    if node.winner_team_id == winner:
        return False
    node.winner_team_id, node.loser_team_id = winner, loser
    node.advancing_team_id, node.eliminated_or_safe_team_id = winner, loser
    node.tiebreaker_used, node.status, node.finalized_at = tie, "FINAL", now
    bracket = db.get(PostseasonBracket, node.bracket_id)
    _queue_team_notification(
        db, league_id=bracket.league_id, team_id=winner,
        event_type="POSTSEASON_ADVANCED", event_key=f"postseason:advance:{node.id}:{winner}", title="You’re moving on",
        body="You advanced in the postseason.", payload={"postseason_matchup_id": node.id},
    )
    entries = {entry.team_id: entry for entry in db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == node.bracket_id).all()}
    for next_id, slot, team_id in ((node.next_winner_matchup_id, node.next_winner_slot, winner), (node.next_loser_matchup_id, node.next_loser_slot, loser)):
        if next_id is not None and slot:
            _write_participant(db.get(PostseasonMatchup, next_id), slot, team_id, _team_seed(entries, team_id))
    db.flush()
    return True


def reconcile_postseason_correction(db: Session, node: PostseasonMatchup, *, winner_team_id: int, loser_team_id: int, now: datetime | None = None) -> bool:
    """Repair a correction only while all dependent games remain unstarted."""
    now = now or utcnow()
    bracket = db.get(PostseasonBracket, node.bracket_id)
    dependents = [db.get(PostseasonMatchup, item) for item in (node.next_winner_matchup_id, node.next_loser_matchup_id) if item]
    started = []
    for downstream in dependents:
        if downstream and downstream.fantasy_matchup_id:
            linked = db.get(Matchup, downstream.fantasy_matchup_id)
            if linked and (linked.status or "").lower() in STARTED_MATCHUP_STATUSES:
                started.append(downstream.id)
    if started:
        bracket.status, bracket.review_reason = "REVIEW_REQUIRED", "stat correction changes a postseason participant after a dependent matchup started"
        bracket.review_metadata_json = {"affected_postseason_matchup_id": node.id, "old_winner_team_id": node.winner_team_id, "corrected_winner_team_id": winner_team_id, "at": now.isoformat()}
        return False
    node.winner_team_id, node.loser_team_id, node.advancing_team_id, node.eliminated_or_safe_team_id = winner_team_id, loser_team_id, winner_team_id, loser_team_id
    entries = {entry.team_id: entry for entry in db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == node.bracket_id).all()}
    for next_id, slot, team_id in ((node.next_winner_matchup_id, node.next_winner_slot, winner_team_id), (node.next_loser_matchup_id, node.next_loser_slot, loser_team_id)):
        downstream = db.get(PostseasonMatchup, next_id) if next_id else None
        if downstream and slot:
            _write_participant(downstream, slot, team_id, _team_seed(entries, team_id))
    db.flush()
    materialize_ready_postseason_matchups(db, bracket)
    return True


def calculate_final_standings(db: Session, bracket: PostseasonBracket, *, now: datetime | None = None) -> list[PostseasonFinalStanding]:
    now = now or utcnow()
    nodes = {node.matchup_type: node for node in db.query(PostseasonMatchup).filter(PostseasonMatchup.bracket_id == bracket.id).all()}
    placements: dict[int, tuple[int, str]] = {}
    for matchup_type, first_place in (("CHAMPIONSHIP", 1), ("THIRD_PLACE", 3), ("FIFTH_PLACE", 5), ("SEVENTH_PLACE", 7)):
        node = nodes.get(matchup_type)
        if node and node.status == "FINAL" and node.winner_team_id and node.loser_team_id:
            placements[node.winner_team_id] = (first_place, matchup_type)
            placements[node.loser_team_id] = (first_place + 1, matchup_type)
    entries = db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == bracket.id).order_by(PostseasonEntry.bracket_seed).all()
    if len(placements) != len(entries):
        return []
    league = db.get(League, bracket.league_id)
    ranked = rank_regular_season(db, league, bracket.regular_season_end_week)
    qualifying = {entry.team_id for entry in entries}
    final_order = sorted(placements.items(), key=lambda item: item[1][0]) + [(row.team.id, (len(entries) + index + 1, "REGULAR_SEASON")) for index, row in enumerate(row for row in ranked if row.team.id not in qualifying)]
    existing_rows = db.query(PostseasonFinalStanding).filter(PostseasonFinalStanding.bracket_id == bracket.id).all()
    # A certified correction can swap first/second (or any placement pair).
    # Move existing values to a collision-free temporary range before assigning
    # final places again; the unique (bracket_id, final_place) constraint must
    # remain valid throughout the transaction.
    if existing_rows:
        db.query(PostseasonFinalStanding).filter(PostseasonFinalStanding.bracket_id == bracket.id).update(
            {PostseasonFinalStanding.final_place: -PostseasonFinalStanding.id},
            synchronize_session=False,
        )
        db.flush()
        existing_rows = db.query(PostseasonFinalStanding).filter(PostseasonFinalStanding.bracket_id == bracket.id).all()
    existing = {row.team_id: row for row in existing_rows}
    ranks = {row.team.id: row.rank for row in ranked}; entry_by_team = {entry.team_id: entry for entry in entries}
    postseason_records: dict[int, dict[str, float | int]] = defaultdict(
        lambda: {"wins": 0, "losses": 0, "ties": 0, "points_for": 0.0}
    )
    finalized_nodes = db.query(PostseasonMatchup).filter(
        PostseasonMatchup.bracket_id == bracket.id,
        PostseasonMatchup.status == "FINAL",
        PostseasonMatchup.fantasy_matchup_id.is_not(None),
    ).all()
    for node in finalized_nodes:
        matchup = db.get(Matchup, node.fantasy_matchup_id)
        if matchup is None or node.team_a_id is None or node.team_b_id is None:
            continue
        a_score = float(matchup.home_score if matchup.home_team_id == node.team_a_id else matchup.away_score)
        b_score = float(matchup.away_score if matchup.home_team_id == node.team_a_id else matchup.home_score)
        postseason_records[node.team_a_id]["points_for"] += a_score
        postseason_records[node.team_b_id]["points_for"] += b_score
        # The bracket's stored winner is authoritative for an exact score tie.
        if node.winner_team_id:
            postseason_records[node.winner_team_id]["wins"] += 1
        if node.loser_team_id:
            postseason_records[node.loser_team_id]["losses"] += 1
    for team_id, (place, result) in final_order:
        row = existing.get(team_id) or PostseasonFinalStanding(bracket_id=bracket.id, league_id=bracket.league_id, season=bracket.season, team_id=team_id)
        row.final_place, row.regular_season_rank, row.playoff_seed, row.postseason_result, row.finalized_at = place, ranks[team_id], (entry_by_team.get(team_id).bracket_seed if team_id in entry_by_team else None), result, now
        record = postseason_records[team_id]
        row.wins = int(record["wins"])
        row.losses = int(record["losses"])
        row.ties = int(record["ties"])
        row.points_for = round(float(record["points_for"]), 2)
        db.add(row)
    bracket.status, bracket.finalized_at = "COMPLETED", now
    league.status = "completed"
    champion_team_id = next((team_id for team_id, (place, _result) in final_order if place == 1), None)
    if champion_team_id is not None:
        _queue_team_notification(
            db, league_id=bracket.league_id, team_id=champion_team_id, event_type="POSTSEASON_CHAMPION",
            event_key=f"postseason:champion:{bracket.id}:{champion_team_id}", title="League champion",
            body=f"You won the {league.name} championship.", payload={"bracket_id": bracket.id},
        )
    db.flush()
    return db.query(PostseasonFinalStanding).filter(PostseasonFinalStanding.bracket_id == bracket.id).order_by(PostseasonFinalStanding.final_place).all()


def advance_postseason_state(db: Session, *, now: datetime | None = None) -> dict[str, int]:
    """Existing lifecycle worker entrypoint; safe to repeat after restarts."""
    result = {"planned": 0, "seeded": 0, "advanced": 0, "materialized": 0, "completed": 0, "review_required": 0, "calendar_blocked": 0}
    for league in db.query(League).filter(League.status.in_(("post_draft", "regular_season", "postseason", "completed"))).all():
        try:
            plan = get_or_create_postseason_settings(db, league)
        except ValueError:
            # A partial P4 schedule must block that league's postseason, but
            # never prevent the shared lifecycle worker from advancing other
            # leagues in the same run.
            result["calendar_blocked"] += 1
            continue
        bracket = db.query(PostseasonBracket).filter(PostseasonBracket.league_id == league.id, PostseasonBracket.season == league.season_year).one_or_none()
        if bracket is None:
            result["planned"] += 1
            if regular_season_is_complete(db, league, plan.regular_season_end_week):
                bracket = lock_postseason_seeds(db, league, now=now); result["seeded"] += 1
            continue
        if bracket.status == "SEEDING_PENDING" and regular_season_is_complete(db, league, bracket.regular_season_end_week):
            lock_postseason_seeds(db, league, now=now); result["seeded"] += 1
        # Completed brackets are re-observed for certified stat corrections.
        # A title-game correction has no downstream participant to protect, so
        # final standings and career outcomes can be recalculated safely.
        if bracket.status in {"LOCKED", "ACTIVE", "FINALIZING", "COMPLETED"}:
            refresh_postseason_activity(db, bracket, now=now)
            for node in db.query(PostseasonMatchup).filter(PostseasonMatchup.bracket_id == bracket.id).all():
                result["advanced"] += int(resolve_postseason_matchup(db, node, now=now))
            result["materialized"] += materialize_ready_postseason_matchups(db, bracket)
            if calculate_final_standings(db, bracket, now=now): result["completed"] += 1
        if bracket.status == "REVIEW_REQUIRED": result["review_required"] += 1
    db.commit()
    return result


def postseason_preview(db: Session, league: League) -> dict:
    plan = get_or_create_postseason_settings(db, league)
    ranked = rank_regular_season(db, league, plan.regular_season_end_week)
    return {"is_preview": True, "playoff_cut_line": plan.playoff_team_count, "format_summary": format_summary(plan.playoff_team_count), "teams": ranked, "settings": plan}


def bracket_rows(db: Session, bracket: PostseasonBracket) -> tuple[list[PostseasonEntry], list[PostseasonRound], list[PostseasonMatchup], dict[int, Team], dict[int, User]]:
    entries = db.query(PostseasonEntry).filter(PostseasonEntry.bracket_id == bracket.id).order_by(PostseasonEntry.bracket_seed).all()
    rounds = db.query(PostseasonRound).filter(PostseasonRound.bracket_id == bracket.id).order_by(PostseasonRound.round_number).all()
    nodes = db.query(PostseasonMatchup).filter(PostseasonMatchup.bracket_id == bracket.id).order_by(PostseasonMatchup.round_id, PostseasonMatchup.slot_number).all()
    team_ids = {team_id for node in nodes for team_id in (node.team_a_id, node.team_b_id, node.winner_team_id, node.loser_team_id) if team_id} | {entry.team_id for entry in entries}
    teams = {team.id: team for team in db.query(Team).filter(Team.id.in_(team_ids)).all()} if team_ids else {}
    owner_ids = {team.owner_user_id for team in teams.values() if team.owner_user_id}
    users = {user.id: user for user in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}
    return entries, rounds, nodes, teams, users


def _team_read(team: Team | None, users: dict[int, User]) -> dict | None:
    if team is None:
        return None
    user = users.get(team.owner_user_id or -1)
    return {
        "team_id": team.id,
        "team_name": team.name,
        "manager_name": (user.first_name if user else None) or team.owner_name,
        "manager_avatar_url": user.avatar_url if user else None,
    }


def serialize_postseason(db: Session, league: League) -> dict:
    """One bulk-loaded contract for preview, active bracket, and history."""
    plan = get_or_create_postseason_settings(db, league)
    bracket = db.query(PostseasonBracket).filter(
        PostseasonBracket.league_id == league.id, PostseasonBracket.season == league.season_year
    ).one_or_none()
    if bracket is None:
        preview = postseason_preview(db, league)
        return {
            "league_id": league.id, "season": league.season_year, "status": "SEEDING_PENDING" if regular_season_is_complete(db, league, plan.regular_season_end_week) else "PLANNED",
            "is_preview": True, "playoff_teams": plan.playoff_team_count,
            "regular_season_end_week": plan.regular_season_end_week, "playoff_start_week": plan.playoff_start_week,
            "championship_week": plan.championship_week, "max_rounds": required_rounds(plan.playoff_team_count),
            "calendar_policy_version": plan.calendar_policy_version,
            "calendar_source_identity": plan.calendar_source_identity,
            "calendar_source_revision": plan.calendar_source_revision,
            "calendar_source_sha256": plan.calendar_source_sha256,
            "calendar_source_format_version": plan.calendar_source_format_version,
            "format_version": FIXED_BRACKET_FORMAT_VERSION, "tiebreaker_policy": HIGHER_SEED_TIEBREAKER,
            "format_summary": preview["format_summary"], "playoff_cut_line": plan.playoff_team_count,
            "seeds": [
                {
                    **_team_read(item.team, {}), "seed": item.rank, "regular_season_rank": item.rank,
                    "wins": item.wins, "losses": item.losses, "ties": item.ties, "points_for": item.points_for,
                    "tiebreaker_explanation": item.tiebreaker_explanation,
                }
                for item in preview["teams"]
            ],
            "rounds": [], "final_standings": [],
        }
    entries, rounds, nodes, teams, users = bracket_rows(db, bracket)
    standings = db.query(PostseasonFinalStanding).filter(PostseasonFinalStanding.bracket_id == bracket.id).order_by(PostseasonFinalStanding.final_place).all()
    linked_ids = [row.fantasy_matchup_id for row in nodes if row.fantasy_matchup_id]
    linked = {row.id: row for row in db.query(Matchup).filter(Matchup.id.in_(linked_ids)).all()} if linked_ids else {}
    ranked = rank_regular_season(db, league, bracket.regular_season_end_week)
    records = {row.team.id: row for row in ranked}
    seed_reads = []
    for entry in entries:
        standing = records.get(entry.team_id)
        seed_reads.append({
            **_team_read(teams.get(entry.team_id), users), "seed": entry.bracket_seed, "regular_season_rank": entry.regular_season_rank,
            "wins": standing.wins if standing else 0, "losses": standing.losses if standing else 0,
            "ties": standing.ties if standing else 0, "points_for": standing.points_for if standing else 0.0,
            "tiebreaker_explanation": entry.tiebreaker_explanation,
        })
    round_reads = []
    for round_row in rounds:
        cards = []
        for node in [row for row in nodes if row.round_id == round_row.id]:
            matchup = linked.get(node.fantasy_matchup_id or -1)
            score_for = lambda team_id: (float(matchup.home_score if matchup.home_team_id == team_id else matchup.away_score) if matchup and team_id else None)
            cards.append({
                "id": node.id, "round_number": round_row.round_number, "week": round_row.week,
                "matchup_type": node.matchup_type, "bracket_path": node.bracket_path,
                "status": node.status, "fantasy_matchup_id": node.fantasy_matchup_id,
                "team_a": _team_read(teams.get(node.team_a_id or -1), users), "team_b": _team_read(teams.get(node.team_b_id or -1), users),
                "team_a_seed": node.team_a_seed, "team_b_seed": node.team_b_seed,
                "team_a_score": score_for(node.team_a_id), "team_b_score": score_for(node.team_b_id),
                "winner_team_id": node.winner_team_id, "loser_team_id": node.loser_team_id,
                "tiebreaker_used": node.tiebreaker_used, "next_winner_matchup_id": node.next_winner_matchup_id,
                "next_loser_matchup_id": node.next_loser_matchup_id,
            })
        round_reads.append({"round_number": round_row.round_number, "week": round_row.week, "status": round_row.status, "matchups": cards})
    champion = next((row for row in standings if row.final_place == 1), None)
    return {
        "league_id": league.id, "season": bracket.season, "status": bracket.status, "is_preview": False,
        "playoff_teams": bracket.total_teams, "regular_season_end_week": bracket.regular_season_end_week,
        "playoff_start_week": bracket.playoff_start_week, "format_version": bracket.format_version,
        "championship_week": bracket.championship_week, "max_rounds": bracket.max_rounds,
        "calendar_policy_version": bracket.calendar_policy_version,
        "calendar_source_identity": bracket.calendar_source_identity,
        "calendar_source_revision": bracket.calendar_source_revision,
        "calendar_source_sha256": bracket.calendar_source_sha256,
        "calendar_source_format_version": bracket.calendar_source_format_version,
        "tiebreaker_policy": bracket.tiebreaker_policy, "format_summary": format_summary(bracket.total_teams),
        "seeds_locked_at": bracket.seeds_locked_at, "review_reason": bracket.review_reason, "seeds": seed_reads,
        "playoff_cut_line": bracket.total_teams, "champion": _team_read(teams.get(champion.team_id), users) if champion else None,
        "rounds": round_reads,
        "final_standings": [
            {**_team_read(teams.get(row.team_id), users), "final_place": row.final_place, "regular_season_rank": row.regular_season_rank, "playoff_seed": row.playoff_seed, "postseason_result": row.postseason_result}
            for row in standings
        ],
    }
