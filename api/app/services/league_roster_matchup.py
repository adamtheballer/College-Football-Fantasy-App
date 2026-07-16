from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings as app_settings
from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_invite import LeagueInvite
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_week_score import PlayerWeekScore
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.waiver_claim import WaiverClaim
from collegefootballfantasy_api.app.models.waiver_priority import WaiverPriority
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.schemas.league_flow import (
    LeagueMatchupTabRead,
    LeagueInviteSettingsRead,
    LeagueMemberRead,
    LeagueRosterTabRead,
    LeagueScheduleRowRead,
    LeagueSettingsViewRead,
    LeagueWaiverPlayerRead,
    LeagueWaiversRead,
    MatchupTeamRead,
    RosterTabEntryRead,
    RosterTabTeamRead,
)
from collegefootballfantasy_api.app.schemas.waiver import WaiverDropCandidateRead
from collegefootballfantasy_api.app.services.league_weeks import resolve_current_week
from collegefootballfantasy_api.app.services.league_workspace import build_standings_summary
from collegefootballfantasy_api.app.services.matchup_probability import (
    calculate_matchup_win_probability,
    estimate_player_std_dev,
    is_starting_slot,
)
from collegefootballfantasy_api.app.services.waiver_service import serialize_claims

DEFAULT_ROSTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "K": 1,
    "BENCH": 4,
    "IR": 1,
}


def _slot_limits(db: Session, league: League) -> dict[str, int]:
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    slot_limits = DEFAULT_ROSTER_SLOTS.copy()
    if settings and settings.roster_slots_json:
        slot_limits.update(settings.roster_slots_json)
    return slot_limits


def _owned_team(db: Session, league: League, user: User) -> Team | None:
    return (
        db.query(Team)
        .filter(Team.league_id == league.id, Team.owner_user_id == user.id)
        .first()
    )


def _team_record(db: Session, league: League, team_id: int) -> str:
    latest_week = (
        db.query(func.max(Standing.week))
        .filter(Standing.league_id == league.id, Standing.season == league.season_year)
        .scalar()
    )
    if latest_week is not None:
        standing = (
            db.query(Standing)
            .filter(
                Standing.league_id == league.id,
                Standing.season == league.season_year,
                Standing.week == latest_week,
                Standing.team_id == team_id,
            )
            .first()
        )
        if standing:
            return f"{standing.wins}-{standing.losses}-{standing.ties}"
    return "0-0-0"


def _team_read(db: Session, league: League, team: Team) -> RosterTabTeamRead:
    return RosterTabTeamRead(
        id=team.id,
        name=team.name,
        owner_user_id=team.owner_user_id,
        record=_team_record(db, league, team.id),
    )


def _projection_map(
    db: Session,
    season: int,
    week: int,
    player_ids: set[int],
) -> dict[int, WeeklyProjection]:
    if not player_ids:
        return {}
    rows = (
        db.query(WeeklyProjection)
        .filter(
            WeeklyProjection.season == season,
            WeeklyProjection.week == week,
            WeeklyProjection.player_id.in_(player_ids),
        )
        .all()
    )
    return {row.player_id: row for row in rows}


def _roster_rows(db: Session, team_id: int) -> list[RosterEntry]:
    return (
        db.query(RosterEntry)
        .filter(RosterEntry.team_id == team_id)
        .order_by(RosterEntry.slot.asc(), RosterEntry.id.asc())
        .all()
    )


def _serialize_roster_entry(
    entry: RosterEntry,
    projection: WeeklyProjection | None,
    opponent: str | None = None,
) -> RosterTabEntryRead:
    slot = (entry.slot or "BENCH").upper()
    projected = float(projection.fantasy_points or 0.0) if projection else 0.0
    floor = float(projection.floor or 0.0) if projection else 0.0
    ceiling = float(projection.ceiling or 0.0) if projection else 0.0
    return RosterTabEntryRead(
        id=entry.id,
        league_id=entry.league_id,
        team_id=entry.team_id,
        fantasy_team_id=entry.team_id,
        fantasy_team_name=entry.team.name if entry.team else None,
        player_id=entry.player_id,
        slot=slot,
        roster_slot=slot,
        status=entry.status,
        is_starter=is_starting_slot(slot),
        is_ir=slot == "IR",
        player_name=entry.player.name if entry.player else None,
        player_school=entry.player.school if entry.player else None,
        player_position=entry.player.position if entry.player else None,
        school=entry.player.school if entry.player else None,
        position=entry.player.position if entry.player else None,
        projected_points=projected,
        floor=floor,
        ceiling=ceiling,
        boom_prob=float(projection.boom_prob or 0.0) if projection else 0.0,
        bust_prob=float(projection.bust_prob or 0.0) if projection else 0.0,
        opponent=opponent,
        weekly_projected_fantasy_points=projected,
    )


def _serialize_team_roster(
    db: Session,
    league: League,
    team: Team,
    week: int,
    opponent: str | None = None,
) -> list[RosterTabEntryRead]:
    entries = _roster_rows(db, team.id)
    projection_by_player = _projection_map(
        db,
        league.season_year,
        week,
        {entry.player_id for entry in entries},
    )
    return [
        _serialize_roster_entry(entry, projection_by_player.get(entry.player_id), opponent)
        for entry in entries
    ]


def _starter_projection_summary(roster: list[RosterTabEntryRead]) -> tuple[float, float]:
    total = 0.0
    variance = 0.0
    for entry in roster:
        if not entry.is_starter:
            continue
        total += entry.projected_points
        std_dev = estimate_player_std_dev(entry.projected_points, entry.floor, entry.ceiling)
        variance += std_dev * std_dev
    return round(total, 2), variance


def build_roster_tab_view(
    db: Session,
    league: League,
    user: User,
    selected_week: int | None = None,
) -> LeagueRosterTabRead:
    week = resolve_current_week(db, league, selected_week)
    team = _owned_team(db, league, user)
    slot_limits = _slot_limits(db, league)
    if not team:
        return LeagueRosterTabRead(
            league_id=league.id,
            season=league.season_year,
            week=week,
            owned_team=None,
            roster=[],
            data=[],
            roster_slot_limits=slot_limits,
            ir_slots=int(slot_limits.get("IR", 0)),
            message="No team found for your user in this league.",
        )

    matchup = (
        db.query(Matchup)
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            Matchup.week == week,
            (Matchup.home_team_id == team.id) | (Matchup.away_team_id == team.id),
        )
        .first()
    )
    opponent_name = None
    if matchup:
        opponent_id = matchup.away_team_id if matchup.home_team_id == team.id else matchup.home_team_id
        opponent = db.get(Team, opponent_id)
        opponent_name = opponent.name if opponent else None

    roster = _serialize_team_roster(db, league, team, week, opponent_name)
    team_read = _team_read(db, league, team)
    return LeagueRosterTabRead(
        league_id=league.id,
        season=league.season_year,
        week=week,
        owned_team=team_read,
        fantasy_team_id=team.id,
        fantasy_team_name=team.name,
        roster=roster,
        data=roster,
        roster_slot_limits=slot_limits,
        ir_slots=int(slot_limits.get("IR", 0)),
        message=None if roster else "Roster is empty. It will populate after the draft.",
    )


def build_matchup_tab_view(
    db: Session,
    league: League,
    user: User,
    selected_week: int | None = None,
) -> LeagueMatchupTabRead:
    week = resolve_current_week(db, league, selected_week)
    team = _owned_team(db, league, user)
    if not team:
        return LeagueMatchupTabRead(
            league_id=league.id,
            season=league.season_year,
            week=week,
            my_roster=[],
            opponent_roster=[],
            message="No team found for your user in this league.",
        )

    matchup = (
        db.query(Matchup)
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            Matchup.week == week,
            (Matchup.home_team_id == team.id) | (Matchup.away_team_id == team.id),
        )
        .first()
    )
    if not matchup:
        my_roster = _serialize_team_roster(db, league, team, week)
        my_total, my_variance = _starter_projection_summary(my_roster)
        my_prob, opponent_prob = calculate_matchup_win_probability(my_total, my_total, my_variance, my_variance)
        my_team = MatchupTeamRead(
            id=team.id,
            name=team.name,
            record=_team_record(db, league, team.id),
            projected_points=my_total,
            win_probability=my_prob,
            fantasy_team_id=team.id,
            fantasy_team_name=team.name,
            projected_total=my_total,
            roster=my_roster,
        )
        return LeagueMatchupTabRead(
            league_id=league.id,
            season=league.season_year,
            week=week,
            status=None,
            my_team=my_team,
            user_team=my_team,
            opponent_team=None,
            my_roster=my_roster,
            opponent_roster=[],
            message="No matchup generated yet.",
        )

    opponent_id = matchup.away_team_id if matchup.home_team_id == team.id else matchup.home_team_id
    opponent = db.get(Team, opponent_id)
    opponent_name = opponent.name if opponent else "TBD"
    my_roster = _serialize_team_roster(db, league, team, week, opponent_name)
    opponent_roster = _serialize_team_roster(db, league, opponent, week, team.name) if opponent else []
    my_total, my_variance = _starter_projection_summary(my_roster)
    opponent_total, opponent_variance = _starter_projection_summary(opponent_roster)
    status = (matchup.status or "").lower()
    use_scored_totals = status in {"live", "final", "stat_corrected"}
    if use_scored_totals:
        if matchup.home_team_id == team.id:
            my_total = float(matchup.home_score or 0.0)
            opponent_total = float(matchup.away_score or 0.0)
        else:
            my_total = float(matchup.away_score or 0.0)
            opponent_total = float(matchup.home_score or 0.0)
    my_probability, opponent_probability = calculate_matchup_win_probability(
        my_total,
        opponent_total,
        my_variance,
        opponent_variance,
    )

    my_team = MatchupTeamRead(
        id=team.id,
        name=team.name,
        record=_team_record(db, league, team.id),
        projected_points=my_total,
        win_probability=my_probability,
        fantasy_team_id=team.id,
        fantasy_team_name=team.name,
        projected_total=my_total,
        roster=my_roster,
    )
    opponent_team = (
        MatchupTeamRead(
            id=opponent.id,
            name=opponent.name,
            record=_team_record(db, league, opponent.id),
            projected_points=opponent_total,
            win_probability=opponent_probability,
            fantasy_team_id=opponent.id,
            fantasy_team_name=opponent.name,
            projected_total=opponent_total,
            roster=opponent_roster,
        )
        if opponent
        else None
    )
    return LeagueMatchupTabRead(
        league_id=league.id,
        season=league.season_year,
        week=week,
        matchup_id=matchup.id,
        status=matchup.status,
        my_team=my_team,
        user_team=my_team,
        opponent_team=opponent_team,
        my_roster=my_roster,
        opponent_roster=opponent_roster,
        projection_source="live_scoring" if use_scored_totals else "weekly_projections",
        message=None,
    )


def build_waivers_view(
    db: Session,
    league: League,
    user: User,
    limit: int = 50,
    offset: int = 0,
    selected_week: int | None = None,
) -> LeagueWaiversRead:
    week = resolve_current_week(db, league, selected_week)
    team = _owned_team(db, league, user)
    unavailable_player_ids = {
        player_id
        for (player_id,) in db.query(RosterEntry.player_id)
        .filter(RosterEntry.league_id == league.id)
        .all()
    }
    draft = db.query(Draft).filter(Draft.league_id == league.id).first()
    if draft:
        unavailable_player_ids.update(
            player_id
            for (player_id,) in db.query(DraftPick.player_id)
            .filter(DraftPick.draft_id == draft.id)
            .all()
        )
    query = db.query(Player).filter(~Player.id.in_(unavailable_player_ids)).order_by(
        Player.sheet_projected_season_points.desc().nullslast(),
        Player.name.asc(),
    )
    total = query.count()
    players = query.offset(max(0, offset)).limit(max(1, min(limit, 100))).all()
    player_ids = {player.id for player in players}
    projection_by_player = _projection_map(db, league.season_year, week, player_ids)
    score_by_player = {
        row.player_id: row
        for row in db.query(PlayerWeekScore)
        .filter(
            PlayerWeekScore.league_id == league.id,
            PlayerWeekScore.season == league.season_year,
            PlayerWeekScore.week == week,
            PlayerWeekScore.player_id.in_(player_ids or {0}),
        )
        .all()
    }
    claims = []
    roster = []
    waiver_priority = None
    faab_remaining = None
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if team:
        priority_row = (
            db.query(WaiverPriority)
            .filter(WaiverPriority.league_id == league.id, WaiverPriority.team_id == team.id)
            .first()
        )
        waiver_priority = priority_row.priority if priority_row else None
        faab_remaining = priority_row.faab_remaining if priority_row else (settings.faab_budget if settings else 100)
        claim_rows = (
            db.query(WaiverClaim)
            .filter(WaiverClaim.league_id == league.id, WaiverClaim.team_id == team.id)
            .order_by(WaiverClaim.created_at.desc(), WaiverClaim.id.desc())
            .limit(25)
            .all()
        )
        claims = serialize_claims(db, claim_rows)
        roster = [
            WaiverDropCandidateRead(
                roster_entry_id=entry.id,
                player_id=entry.player_id,
                player_name=entry.player.name if entry.player else "Unknown Player",
                position=entry.player.position if entry.player else None,
                school=entry.player.school if entry.player else None,
                slot=entry.slot,
            )
            for entry in _roster_rows(db, team.id)
        ]
    return LeagueWaiversRead(
        league_id=league.id,
        fantasy_team_id=team.id if team else None,
        waiver_priority=waiver_priority,
        faab_remaining=faab_remaining,
        available_players=[
            LeagueWaiverPlayerRead(
                id=player.id,
                name=player.name,
                school=player.school,
                position=player.position,
                weekly_projected_fantasy_points=float(
                    score_by_player[player.id].fantasy_points
                    if player.id in score_by_player
                    else projection_by_player[player.id].fantasy_points
                    if player.id in projection_by_player
                    else 0.0
                ),
            )
            for player in players
        ],
        claims=claims,
        roster=roster,
        waiver_rules={
            "waiver_type": settings.waiver_type if settings else "FAAB",
            "waiver_period_hours": settings.waiver_period_hours if settings else 24,
            "faab_budget": settings.faab_budget if settings else 100,
        },
        total_available=total,
        message=None if team else "No team found for your user in this league.",
    )


def build_settings_view(db: Session, league: League, user: User) -> LeagueSettingsViewRead:
    settings = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    members = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).all()
    teams = db.query(Team).filter(Team.league_id == league.id).order_by(Team.id.asc()).all()
    roster_entries = (
        db.query(RosterEntry)
        .filter(RosterEntry.league_id == league.id)
        .order_by(RosterEntry.team_id.asc(), RosterEntry.slot.asc(), RosterEntry.id.asc())
        .all()
    )
    projection_by_player = _projection_map(
        db,
        league.season_year,
        resolve_current_week(db, league),
        {entry.player_id for entry in roster_entries},
    )
    roster_rows = [
        _serialize_roster_entry(entry, projection_by_player.get(entry.player_id))
        for entry in roster_entries
    ]
    standings = [
        row.model_dump()
        for row in build_standings_summary(db, league)
    ]
    schedule_rows = (
        db.query(Matchup, Team.name, Team.id)
        .join(Team, Team.id == Matchup.home_team_id)
        .filter(Matchup.league_id == league.id, Matchup.season == league.season_year)
        .order_by(Matchup.week.asc(), Matchup.id.asc())
        .all()
    )
    away_names = {team.id: team.name for team in teams}
    schedule = [
        LeagueScheduleRowRead(
            matchup_id=matchup.id,
            week=matchup.week,
            home_team_id=matchup.home_team_id,
            home_team_name=home_name,
            away_team_id=matchup.away_team_id,
            away_team_name=away_names.get(matchup.away_team_id, "TBD"),
            home_projected_total=float(matchup.home_score or 0.0),
            away_projected_total=float(matchup.away_score or 0.0),
            home_win_probability=50.0,
            away_win_probability=50.0,
        )
        for matchup, home_name, _home_id in schedule_rows
    ]
    draft = db.query(Draft).filter(Draft.league_id == league.id).first()
    draft_status = (draft.status if draft else None) or league.status
    draft_is_complete = (draft_status or "").lower() in {"completed", "complete", "final", "closed"} or league.status == "post_draft"
    active_invite = (
        db.query(LeagueInvite)
        .filter(LeagueInvite.league_id == league.id, LeagueInvite.active.is_(True))
        .order_by(LeagueInvite.created_at.desc(), LeagueInvite.id.desc())
        .first()
    )
    invite_code = league.invite_code or (active_invite.code if active_invite else None)
    invite = None
    if league.commissioner_user_id == user.id and invite_code and not draft_is_complete:
        invite = LeagueInviteSettingsRead(
            code=invite_code,
            link=f"{app_settings.ui_base_url.rstrip('/')}/join/{invite_code}",
            draft_status=draft_status,
            visible_until_draft_complete=True,
        )
    draft_results: list[dict] = []
    if draft:
        pick_rows = (
            db.query(DraftPick, Team, Player)
            .join(Team, Team.id == DraftPick.team_id)
            .join(Player, Player.id == DraftPick.player_id)
            .filter(DraftPick.draft_id == draft.id)
            .order_by(DraftPick.overall_pick.asc())
            .all()
        )
        draft_results = [
            {
                "overall_pick": pick.overall_pick,
                "round_number": pick.round_number,
                "round_pick": pick.round_pick,
                "team_id": team.id,
                "team_name": team.name,
                "player_id": player.id,
                "player_name": player.name,
                "position": player.position,
            }
            for pick, team, player in pick_rows
        ]

    return LeagueSettingsViewRead(
        league_id=league.id,
        league_name=league.name,
        league_info={
            "name": league.name,
            "season": league.season_year,
            "status": league.status,
            "max_teams": league.max_teams,
            "is_private": league.is_private,
            "commissioner_user_id": league.commissioner_user_id,
        },
        invite=invite,
        members=[LeagueMemberRead.model_validate(member) for member in members],
        scoring_settings=settings.scoring_json if settings else {},
        roster_settings=settings.roster_slots_json if settings and settings.roster_slots_json else DEFAULT_ROSTER_SLOTS.copy(),
        waiver_rules={
            "waiver_type": settings.waiver_type if settings else "FAAB",
            "waiver_period_hours": settings.waiver_period_hours if settings else 24,
            "trade_review_type": settings.trade_review_type if settings else "commissioner",
        },
        standings=standings,
        schedule=schedule,
        rosters=roster_rows,
        draft_results=draft_results,
        commissioner_controls=(
            ["reschedule_draft", "update_settings", "regenerate_invite"]
            if league.commissioner_user_id == user.id
            else []
        ),
    )
