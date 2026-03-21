from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.league_flow import (
    DraftRead,
    LeagueDetailRead,
    LeagueMemberRead,
    LeagueSettingsRead,
    LeagueWorkspaceMatchupSummaryRead,
    LeagueWorkspaceRead,
    LeagueWorkspaceRosterEntryRead,
    LeagueWorkspaceStandingSummaryRead,
    LeagueWorkspaceTeamRead,
)


def get_league_detail(db: Session, league: League) -> LeagueDetailRead:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")

    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    members_rows = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).all()

    return LeagueDetailRead(
        id=league.id,
        name=league.name,
        commissioner_user_id=league.commissioner_user_id,
        season_year=league.season_year,
        max_teams=league.max_teams,
        is_private=league.is_private,
        invite_code=league.invite_code,
        description=league.description,
        icon_url=league.icon_url,
        status=league.status,
        created_at=league.created_at,
        updated_at=league.updated_at,
        settings=LeagueSettingsRead.model_validate(settings_row),
        draft=DraftRead.model_validate(draft_row) if draft_row else None,
        members=[LeagueMemberRead.model_validate(m) for m in members_rows],
    )


def build_allowed_actions(
    league: League, membership: LeagueMember, owned_team: Team | None
) -> list[str]:
    allowed_actions = {
        "open_draft_lobby",
        "view_members",
        "view_standings",
    }
    if owned_team:
        allowed_actions.update({"view_roster", "manage_roster", "manage_team"})
    if membership.role == "commissioner" or league.commissioner_user_id == membership.user_id:
        allowed_actions.update(
            {"update_settings", "regenerate_invite", "reschedule_draft", "delete_league"}
        )
    return sorted(allowed_actions)


def build_matchup_summary(
    db: Session,
    league: League,
    owned_team: Team | None,
) -> LeagueWorkspaceMatchupSummaryRead | None:
    if not owned_team:
        return None

    matchup_rows = (
        db.query(Matchup)
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            (Matchup.home_team_id == owned_team.id) | (Matchup.away_team_id == owned_team.id),
        )
        .all()
    )
    if not matchup_rows:
        return None

    def matchup_sort_key(row: Matchup) -> tuple[int, int]:
        status_priority = 0 if row.status in {"scheduled", "live", "projected"} else 1
        return (status_priority, row.week)

    matchup = sorted(matchup_rows, key=matchup_sort_key)[0]
    is_home = matchup.home_team_id == owned_team.id
    opponent_team_id = matchup.away_team_id if is_home else matchup.home_team_id
    opponent = db.get(Team, opponent_team_id)

    return LeagueWorkspaceMatchupSummaryRead(
        week=matchup.week,
        team_id=owned_team.id,
        opponent_team_id=opponent_team_id,
        opponent_team_name=opponent.name if opponent else None,
        status=matchup.status,
        projected_points_for=matchup.home_score if is_home else matchup.away_score,
        projected_points_against=matchup.away_score if is_home else matchup.home_score,
    )


def build_standings_summary(db: Session, league: League) -> list[LeagueWorkspaceStandingSummaryRead]:
    latest_week = (
        db.query(func.max(Standing.week))
        .filter(Standing.league_id == league.id, Standing.season == league.season_year)
        .scalar()
    )
    if latest_week is not None:
        standings_rows = (
            db.query(Standing, Team)
            .join(Team, Team.id == Standing.team_id)
            .filter(
                Standing.league_id == league.id,
                Standing.season == league.season_year,
                Standing.week == latest_week,
            )
            .all()
        )
        ordered_rows = sorted(
            standings_rows,
            key=lambda row: (-row[0].wins, row[0].losses, -row[0].points_for, row[1].name),
        )
        return [
            LeagueWorkspaceStandingSummaryRead(
                team_id=standing.team_id,
                team_name=team.name,
                wins=standing.wins,
                losses=standing.losses,
                ties=standing.ties,
                points_for=standing.points_for,
                rank=index,
            )
            for index, (standing, team) in enumerate(ordered_rows, start=1)
        ]

    teams = db.query(Team).filter(Team.league_id == league.id).all()
    team_stats = {
        team.id: {
            "team": team,
            "wins": 0,
            "losses": 0,
            "ties": 0,
            "points_for": 0.0,
        }
        for team in teams
    }
    matchup_rows = (
        db.query(Matchup)
        .filter(Matchup.league_id == league.id, Matchup.season == league.season_year)
        .all()
    )
    for matchup in matchup_rows:
        home_stats = team_stats.get(matchup.home_team_id)
        away_stats = team_stats.get(matchup.away_team_id)
        if not home_stats or not away_stats:
            continue
        home_stats["points_for"] += float(matchup.home_score or 0.0)
        away_stats["points_for"] += float(matchup.away_score or 0.0)
        if matchup.status != "final":
            continue
        if matchup.home_score > matchup.away_score:
            home_stats["wins"] += 1
            away_stats["losses"] += 1
        elif matchup.home_score < matchup.away_score:
            away_stats["wins"] += 1
            home_stats["losses"] += 1
        else:
            home_stats["ties"] += 1
            away_stats["ties"] += 1

    ordered_rows = sorted(
        team_stats.values(),
        key=lambda row: (-row["wins"], row["losses"], -row["points_for"], row["team"].name),
    )
    return [
        LeagueWorkspaceStandingSummaryRead(
            team_id=row["team"].id,
            team_name=row["team"].name,
            wins=int(row["wins"]),
            losses=int(row["losses"]),
            ties=int(row["ties"]),
            points_for=float(row["points_for"]),
            rank=index,
        )
        for index, row in enumerate(ordered_rows, start=1)
    ]


def build_league_workspace(
    db: Session,
    league: League,
    membership: LeagueMember,
    current_user: User,
) -> LeagueWorkspaceRead:
    owned_team = (
        db.query(Team)
        .filter(Team.league_id == league.id, Team.owner_user_id == current_user.id)
        .first()
    )
    roster_entries: list[LeagueWorkspaceRosterEntryRead] = []
    if owned_team:
        roster_rows = db.query(RosterEntry).filter(RosterEntry.team_id == owned_team.id).all()
        roster_entries = [
            LeagueWorkspaceRosterEntryRead(
                id=row.id,
                team_id=row.team_id,
                player_id=row.player_id,
                slot=row.slot,
                status=row.status,
                player_name=row.player.name if row.player else None,
                player_school=row.player.school if row.player else None,
                player_position=row.player.position if row.player else None,
            )
            for row in roster_rows
        ]

    return LeagueWorkspaceRead(
        league=get_league_detail(db, league),
        membership=LeagueMemberRead.model_validate(membership),
        owned_team=(
            LeagueWorkspaceTeamRead(
                id=owned_team.id,
                league_id=owned_team.league_id,
                name=owned_team.name,
                owner_user_id=owned_team.owner_user_id,
            )
            if owned_team
            else None
        ),
        roster=roster_entries,
        matchup_summary=build_matchup_summary(db, league, owned_team),
        standings_summary=build_standings_summary(db, league),
        allowed_actions=build_allowed_actions(league, membership, owned_team),
    )
