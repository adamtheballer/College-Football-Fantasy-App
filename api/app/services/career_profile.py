"""Server-derived CFB Fantasy career profile summaries.

This module deliberately reads the league, matchup, standing, draft, trade and
waiver ledgers directly.  Career events are an auditable timeline, not a second
source of truth for scoring or roster ownership.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.career import LeagueRivalry, UserCareerEvent
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.mock_draft import MockDraft
from collegefootballfantasy_api.app.models.postseason import PostseasonFinalStanding
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.schemas.career import (
    CareerEventRead,
    CareerLeagueRead,
    CareerPublicProfileRead,
    CareerProfileRead,
    CareerRecordRead,
    CareerTrophyRead,
)

FINAL_MATCHUP_STATUSES = {"final", "completed", "complete", "stat_corrected"}
PROCESSED_TRADE_STATUSES = {"processed", "complete", "completed"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def record_career_event(
    db: Session,
    *,
    user_id: int,
    event_type: str,
    source_key: str,
    title: str,
    occurred_at: datetime | None = None,
    league_id: int | None = None,
    team_id: int | None = None,
    matchup_id: int | None = None,
    trade_id: int | None = None,
    draft_id: int | None = None,
    season: int | None = None,
    week: int | None = None,
    metadata: dict | None = None,
) -> UserCareerEvent:
    """Append one immutable event, safely ignoring an already-recorded source."""
    existing = db.query(UserCareerEvent).filter(UserCareerEvent.source_key == source_key).one_or_none()
    if existing is not None:
        return existing
    event = UserCareerEvent(
        user_id=user_id,
        event_type=event_type,
        source_key=source_key,
        title=title,
        occurred_at=occurred_at or utcnow(),
        league_id=league_id,
        team_id=team_id,
        matchup_id=matchup_id,
        trade_id=trade_id,
        draft_id=draft_id,
        season=season,
        week=week,
        metadata_json=metadata or {},
    )
    db.add(event)
    return event


def record_finalized_matchup_events(db: Session, matchups: list[Matchup]) -> int:
    """Append one final-result career event per human manager, idempotently.

    Matchup and team-score tables remain the source of truth.  These events are
    only the durable, auditable activity timeline shown on a career profile.
    """
    if not matchups:
        return 0
    team_ids = {team_id for row in matchups for team_id in (row.home_team_id, row.away_team_id)}
    teams = {row.id: row for row in db.query(Team).filter(Team.id.in_(team_ids), Team.owner_user_id.is_not(None)).all()}
    active_rivalries = {
        row.team_id: row
        for row in db.query(LeagueRivalry).filter(
            LeagueRivalry.team_id.in_(team_ids), LeagueRivalry.active.is_(True)
        ).all()
    }
    created = 0
    for matchup in matchups:
        if (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
            continue
        for team_id, own_score, opponent_score in (
            (matchup.home_team_id, matchup.home_score, matchup.away_score),
            (matchup.away_team_id, matchup.away_score, matchup.home_score),
        ):
            team = teams.get(team_id)
            if team is None:
                continue
            result = "W" if own_score > opponent_score else "L" if own_score < opponent_score else "T"
            source_key = f"matchup:final:{matchup.id}:team:{team.id}"
            before = db.query(UserCareerEvent.id).filter(UserCareerEvent.source_key == source_key).first()
            record_career_event(
                db,
                user_id=team.owner_user_id,
                event_type="MATCHUP_FINALIZED",
                source_key=source_key,
                title=f"Week {matchup.week} {result} ({own_score:.1f}-{opponent_score:.1f})",
                league_id=matchup.league_id,
                team_id=team.id,
                matchup_id=matchup.id,
                season=matchup.season,
                week=matchup.week,
                metadata={"result": result, "points_for": own_score, "points_against": opponent_score},
            )
            created += int(before is None)
            rivalry = active_rivalries.get(team.id)
            if rivalry is not None and rivalry.league_id == matchup.league_id and rivalry.season == matchup.season:
                opponent_team_id = matchup.away_team_id if matchup.home_team_id == team.id else matchup.home_team_id
                if opponent_team_id == rivalry.rival_team_id:
                    rival_source_key = f"rival:matchup:{matchup.id}:team:{team.id}"
                    rival_before = db.query(UserCareerEvent.id).filter(UserCareerEvent.source_key == rival_source_key).first()
                    result_event = {"W": "RIVAL_MATCHUP_WON", "L": "RIVAL_MATCHUP_LOST", "T": "RIVAL_MATCHUP_TIED"}[result]
                    record_career_event(
                        db,
                        user_id=team.owner_user_id,
                        event_type=result_event,
                        source_key=rival_source_key,
                        title=f"Rival Week {result} ({own_score:.1f}-{opponent_score:.1f})",
                        league_id=matchup.league_id,
                        team_id=team.id,
                        matchup_id=matchup.id,
                        season=matchup.season,
                        week=matchup.week,
                        metadata={"result": result, "rival_team_id": opponent_team_id},
                    )
                    created += int(rival_before is None)
    return created


def _record_from_matchups(matchups: list[Matchup], team_ids: set[int]) -> tuple[CareerRecordRead, int, int, int]:
    wins = losses = ties = 0
    longest = current = longest_loss = current_loss = 0
    for matchup in sorted(matchups, key=lambda row: (row.season, row.week, row.id)):
        if (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
            continue
        if matchup.home_team_id not in team_ids and matchup.away_team_id not in team_ids:
            continue
        is_home = matchup.home_team_id in team_ids
        own_score = matchup.home_score if is_home else matchup.away_score
        opponent_score = matchup.away_score if is_home else matchup.home_score
        if own_score > opponent_score:
            wins += 1
            current += 1
            longest = max(longest, current)
            current_loss = 0
        elif own_score < opponent_score:
            losses += 1
            current = 0
            current_loss += 1
            longest_loss = max(longest_loss, current_loss)
        else:
            ties += 1
            current = 0
            current_loss = 0
    total = wins + losses + ties
    # Tie treatment is one-half of a win, consistently across the product.
    return (
        CareerRecordRead(
            wins=wins,
            losses=losses,
            ties=ties,
            win_pct=round((wins + ties * 0.5) / total, 3) if total else 0.0,
        ),
        longest,
        longest_loss,
        current,
    )


def _team_points(db: Session, team_ids: set[int]) -> tuple[float, float | None, float | None, int]:
    if not team_ids:
        return 0.0, None, None, 0
    rows = db.query(TeamWeekScore).filter(TeamWeekScore.team_id.in_(team_ids)).all()
    values = [float(row.total_points or row.points_total or 0.0) for row in rows]
    return (
        round(sum(values), 2),
        round(max(values), 2) if values else None,
        round(min(values), 2) if values else None,
        len(values),
    )


def _league_record(matchups: list[Matchup], team_id: int) -> CareerRecordRead:
    record, _, _, _ = _record_from_matchups(matchups, {team_id})
    return record


def build_career_profile(db: Session, user: User) -> CareerProfileRead:
    teams = db.query(Team).filter(Team.owner_user_id == user.id).all()
    team_ids = {team.id for team in teams}
    league_ids = {team.league_id for team in teams}
    memberships = db.query(LeagueMember).filter(LeagueMember.user_id == user.id).all()
    member_league_ids = {membership.league_id for membership in memberships}
    all_league_ids = league_ids | member_league_ids
    leagues = db.query(League).filter(League.id.in_(all_league_ids)).all() if all_league_ids else []
    member_leagues = [league for league in leagues if league.id in member_league_ids]
    matchups = db.query(Matchup).filter(Matchup.league_id.in_(league_ids)).all() if league_ids else []
    record, longest_streak, longest_loss_streak, current_streak = _record_from_matchups(matchups, team_ids)
    total_points, high_week, low_week, scored_weeks = _team_points(db, team_ids)

    completed_leagues = sum(
        (league.status or "").lower() in {"complete", "completed", "postseason_complete"}
        for league in member_leagues
    )
    drafts_completed = db.query(Draft).filter(Draft.league_id.in_(league_ids), Draft.status == "completed").count() if league_ids else 0
    trade_query = db.query(TradeOffer).filter(
        TradeOffer.league_id.in_(league_ids),
        (TradeOffer.proposing_team_id.in_(team_ids)) | (TradeOffer.receiving_team_id.in_(team_ids)),
    ) if team_ids else None
    trades_completed = trade_query.filter(TradeOffer.status.in_(PROCESSED_TRADE_STATUSES)).count() if trade_query is not None else 0
    trades_proposed = trade_query.filter(TradeOffer.created_by_user_id == user.id).count() if trade_query is not None else 0
    trades_accepted = trade_query.filter(TradeOffer.accepted_at.is_not(None)).count() if trade_query is not None else 0
    waiver_wins = db.query(WaiverClaim).filter(WaiverClaim.team_id.in_(team_ids), WaiverClaim.status == "won").count() if team_ids else 0
    standings = db.query(PostseasonFinalStanding).filter(PostseasonFinalStanding.team_id.in_(team_ids)).all() if team_ids else []
    championships = sum(row.final_place == 1 for row in standings)
    playoff_appearances = len(standings)
    regular_season_first_place = sum(row.regular_season_rank == 1 for row in standings)
    completed_matchups = record.wins + record.losses + record.ties
    mock_completed = db.query(MockDraft).filter(MockDraft.owner_user_id == user.id, MockDraft.status == "completed").count()
    active_rivalries = db.query(LeagueRivalry).filter(
        LeagueRivalry.team_id.in_(team_ids), LeagueRivalry.active.is_(True)
    ).all() if team_ids else []
    rivalry_results = {"wins": 0, "losses": 0, "ties": 0}
    if active_rivalries:
        rivalry_pairs = {(row.team_id, row.rival_team_id) for row in active_rivalries}
        for matchup in matchups:
            if (matchup.status or "").lower() not in FINAL_MATCHUP_STATUSES:
                continue
            for own_team_id, rival_team_id in rivalry_pairs:
                if {matchup.home_team_id, matchup.away_team_id} != {own_team_id, rival_team_id}:
                    continue
                own_score, rival_score = (
                    (matchup.home_score, matchup.away_score)
                    if matchup.home_team_id == own_team_id
                    else (matchup.away_score, matchup.home_score)
                )
                if own_score > rival_score:
                    rivalry_results["wins"] += 1
                elif own_score < rival_score:
                    rivalry_results["losses"] += 1
                else:
                    rivalry_results["ties"] += 1

    return CareerProfileRead(
        user_id=user.id,
        display_name=user.first_name,
        username=user.username,
        member_since=user.created_at,
        record=record,
        leagues={"joined": len(member_league_ids), "total": len(member_league_ids), "active": len(member_leagues) - completed_leagues, "completed": completed_leagues},
        drafts={"official_completed": drafts_completed, "completed": drafts_completed, "mock_completed": mock_completed},
        trades={"proposed": trades_proposed, "accepted": trades_accepted, "completed": trades_completed},
        waivers={"won": waiver_wins},
        postseason={
            "appearances": playoff_appearances,
            "championships": championships,
            "regular_season_first_place": regular_season_first_place,
        },
        matchups={"completed": completed_matchups},
        scoring={
            "points_for": total_points,
            "average_points": round(total_points / scored_weeks, 2) if scored_weeks else 0.0,
            "high_week": high_week,
            "low_week": low_week,
        },
        streaks={"longest_win": longest_streak, "longest_loss": longest_loss_streak, "current_win": current_streak},
        rivalry={"active": len(active_rivalries), **rivalry_results},
    )


def build_public_career_profile(db: Session, user: User) -> CareerPublicProfileRead:
    """Return only the fields intended for another authenticated manager."""
    profile = build_career_profile(db, user)
    return CareerPublicProfileRead(
        user_id=profile.user_id,
        display_name=profile.display_name,
        username=profile.username,
        member_since=profile.member_since,
        record=profile.record,
        leagues={key: profile.leagues[key] for key in ("joined", "total", "completed") if key in profile.leagues},
        drafts={key: profile.drafts[key] for key in ("official_completed", "mock_completed") if key in profile.drafts},
        trades={"completed": profile.trades["completed"]},
        postseason=profile.postseason,
    )


def list_career_events(db: Session, user_id: int, *, limit: int = 50, offset: int = 0) -> tuple[list[CareerEventRead], int]:
    query = db.query(UserCareerEvent).filter(UserCareerEvent.user_id == user_id)
    total = query.count()
    rows = query.order_by(UserCareerEvent.occurred_at.desc(), UserCareerEvent.id.desc()).offset(offset).limit(limit).all()
    return [
        CareerEventRead(
            id=row.id, event_type=row.event_type, title=row.title, season=row.season, week=row.week,
            league_id=row.league_id, occurred_at=row.occurred_at, metadata=row.metadata_json or {},
        ) for row in rows
    ], total


def list_career_leagues(db: Session, user_id: int) -> list[CareerLeagueRead]:
    teams = db.query(Team).filter(Team.owner_user_id == user_id).all()
    if not teams:
        return []
    team_ids = {team.id for team in teams}
    leagues = {league.id: league for league in db.query(League).filter(League.id.in_({team.league_id for team in teams})).all()}
    matchups_by_league: dict[int, list[Matchup]] = defaultdict(list)
    for matchup in db.query(Matchup).filter(Matchup.league_id.in_(leagues)).all():
        matchups_by_league[matchup.league_id].append(matchup)
    points_by_team: dict[int, float] = defaultdict(float)
    for score in db.query(TeamWeekScore).filter(TeamWeekScore.team_id.in_(team_ids)).all():
        points_by_team[score.team_id] += float(score.total_points or score.points_total or 0.0)
    finals = {(row.league_id, row.team_id): row for row in db.query(PostseasonFinalStanding).filter(PostseasonFinalStanding.team_id.in_(team_ids)).all()}
    rivalries = {
        (row.league_id, row.team_id): row
        for row in db.query(LeagueRivalry).filter(LeagueRivalry.team_id.in_(team_ids), LeagueRivalry.active.is_(True)).all()
    }
    team_names = {
        row.id: row.name
        for row in db.query(Team).filter(Team.league_id.in_(leagues)).all()
    }
    result: list[CareerLeagueRead] = []
    for team in teams:
        league = leagues[team.league_id]
        final = finals.get((league.id, team.id))
        rivalry = rivalries.get((league.id, team.id))
        rivalry_record = None
        if rivalry is not None:
            rivalry_matchups = [
                row for row in matchups_by_league[league.id]
                if {row.home_team_id, row.away_team_id} == {team.id, rivalry.rival_team_id}
            ]
            rivalry_record = _league_record(rivalry_matchups, team.id)
        result.append(CareerLeagueRead(
            league_id=league.id, name=league.name, season=league.season_year, status=league.status,
            record=_league_record(matchups_by_league[league.id], team.id), points_for=round(points_by_team[team.id], 2),
            final_place=final.final_place if final else None,
            postseason_result=final.postseason_result if final else None,
            rival_team_name=team_names.get(rivalry.rival_team_id) if rivalry else None,
            rival_record=rivalry_record,
        ))
    return sorted(result, key=lambda row: (row.season, row.league_id), reverse=True)


def list_career_trophies(db: Session, user_id: int) -> list[CareerTrophyRead]:
    teams = db.query(Team).filter(Team.owner_user_id == user_id).all()
    if not teams:
        return []
    team_ids = {team.id for team in teams}
    team_by_id = {team.id: team for team in teams}
    trophies: list[CareerTrophyRead] = []
    for final in db.query(PostseasonFinalStanding).filter(PostseasonFinalStanding.team_id.in_(team_ids)).all():
        if final.final_place == 1:
            team = team_by_id[final.team_id]
            trophies.append(CareerTrophyRead(key=f"championship:{final.id}", title="League Champion", season=final.season, league_id=final.league_id, subtitle=team.name))
        elif final.final_place <= 3:
            trophies.append(CareerTrophyRead(key=f"podium:{final.id}", title=f"Finished #{final.final_place}", season=final.season, league_id=final.league_id, subtitle=final.postseason_result))
    return sorted(trophies, key=lambda row: (row.season or 0, row.key), reverse=True)
