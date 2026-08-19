from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.transaction import Transaction
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.league_flow import (
    DraftOrderEntryRead,
    DraftOrderRead,
    DraftRead,
    LeagueDetailRead,
    LeagueListCurrentUserSummaryRead,
    LeagueNewsItem,
    LeagueMemberRead,
    LeaguePowerRankingRow,
    LeagueScoreboardRow,
    LeagueSettingsRead,
    LeagueWorkspaceMatchupSummaryRead,
    LeagueWorkspaceRead,
    LeagueWorkspaceRosterEntryRead,
    LeagueWorkspaceStandingSummaryRead,
    LeagueWorkspaceTeamRead,
)


def get_league_detail(
    db: Session,
    league: League,
    *,
    viewer: User | None = None,
    include_current_user_summary: bool = False,
) -> LeagueDetailRead:
    settings_row = db.query(LeagueSettings).filter(LeagueSettings.league_id == league.id).first()
    if not settings_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="league settings not found")

    draft_row = db.query(Draft).filter(Draft.league_id == league.id).first()
    members_rows = db.query(LeagueMember).filter(LeagueMember.league_id == league.id).all()

    teams = db.query(Team).filter(Team.league_id == league.id).order_by(Team.id.asc()).all()
    manager_ids = {
        user_id
        for user_id in [
            league.commissioner_user_id,
            *(member.user_id for member in members_rows),
            *(team.owner_user_id for team in teams),
        ]
        if user_id is not None
    }
    managers = {
        manager.id: manager
        for manager in db.query(User).filter(User.id.in_(manager_ids)).all()
    } if manager_ids else {}
    draft_order = None
    if draft_row:
        positioned = [team.draft_position for team in teams]
        draft_order = DraftOrderRead(
            draft_order_mode=draft_row.draft_order_mode or "random",
            max_teams=league.max_teams,
            is_complete=(
                len(teams) == league.max_teams
                and set(positioned) == set(range(1, league.max_teams + 1))
            ),
            entries=[
                DraftOrderEntryRead(
                    team_id=team.id,
                    team_name=team.name,
                    owner_user_id=team.owner_user_id,
                    owner_name=team.owner_name,
                    owner_avatar_url=(managers.get(team.owner_user_id).avatar_url if team.owner_user_id else None),
                    draft_position=team.draft_position,
                )
                for team in teams
            ],
        )

    return LeagueDetailRead(
        id=league.id,
        name=league.name,
        commissioner_user_id=league.commissioner_user_id,
        commissioner_name=(managers.get(league.commissioner_user_id).first_name if league.commissioner_user_id in managers else None),
        commissioner_avatar_url=(managers.get(league.commissioner_user_id).avatar_url if league.commissioner_user_id in managers else None),
        season_year=league.season_year,
        max_teams=league.max_teams,
        is_private=league.is_private,
        invite_code=(
            league.invite_code
            if viewer is not None and viewer.id == league.commissioner_user_id
            else None
        ),
        description=league.description,
        icon_url=league.icon_url,
        status=league.status,
        created_at=league.created_at,
        updated_at=league.updated_at,
        settings=LeagueSettingsRead.model_validate(settings_row),
        draft=DraftRead.model_validate(draft_row) if draft_row else None,
        draft_order=draft_order,
        members=[
            LeagueMemberRead(
                id=member.id,
                user_id=member.user_id,
                role=member.role,
                joined_at=member.joined_at,
                manager_name=(managers.get(member.user_id).first_name if member.user_id in managers else None),
                manager_avatar_url=(managers.get(member.user_id).avatar_url if member.user_id in managers else None),
            )
            for member in members_rows
        ],
        current_user_summary=(
            build_league_list_current_user_summary(db, league, viewer)
            if include_current_user_summary and viewer is not None
            else None
        ),
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
    current_user: User,
) -> LeagueWorkspaceMatchupSummaryRead | None:
    if not owned_team:
        return None

    # Import locally to avoid a module cycle: the matchup tab imports the
    # standings helpers in this module. The dashboard intentionally reuses the
    # tab view so total, probability, and selected-week lineup inputs cannot
    # drift between surfaces.
    from collegefootballfantasy_api.app.services.league_roster_matchup import build_matchup_tab_view

    matchup_view = build_matchup_tab_view(db, league, current_user)
    my_team = matchup_view.my_team
    opponent_team = matchup_view.opponent_team
    if my_team is None or opponent_team is None:
        return None

    return LeagueWorkspaceMatchupSummaryRead(
        week=matchup_view.week,
        team_id=my_team.fantasy_team_id,
        opponent_team_id=opponent_team.fantasy_team_id,
        opponent_team_name=opponent_team.fantasy_team_name,
        status=matchup_view.status,
        projected_points_for=my_team.projected_total,
        projected_points_against=opponent_team.projected_total,
        win_probability_for=my_team.win_probability,
        win_probability_against=opponent_team.win_probability,
    )


def build_league_list_current_user_summary(
    db: Session,
    league: League,
    current_user: User,
) -> LeagueListCurrentUserSummaryRead | None:
    """Build the league-card summary from the canonical workspace calculations.

    The list card must never independently calculate records or matchup odds:
    doing so could make it disagree with the League Hub.  Reuse the standings
    and matchup builders that already power that authenticated workspace.
    """

    owned_team = (
        db.query(Team)
        .filter(Team.league_id == league.id, Team.owner_user_id == current_user.id)
        .one_or_none()
    )
    if owned_team is None:
        return None

    standing = next(
        (row for row in build_standings_summary(db, league) if row.team_id == owned_team.id),
        None,
    )
    matchup = build_matchup_summary(db, league, owned_team, current_user)

    return LeagueListCurrentUserSummaryRead(
        team_name=owned_team.name,
        wins=standing.wins if standing else 0,
        losses=standing.losses if standing else 0,
        ties=standing.ties if standing else 0,
        opponent_team_name=matchup.opponent_team_name if matchup else None,
        matchup_week=matchup.week if matchup else None,
        projected_points_for=matchup.projected_points_for if matchup else None,
        projected_points_against=matchup.projected_points_against if matchup else None,
        win_probability_for=matchup.win_probability_for if matchup else None,
        win_probability_against=matchup.win_probability_against if matchup else None,
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


def resolve_default_matchup_week(db: Session, league: League) -> int | None:
    live_or_scheduled_week = (
        db.query(func.min(Matchup.week))
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            Matchup.status.in_(("live", "scheduled", "projected")),
        )
        .scalar()
    )
    if live_or_scheduled_week is not None:
        return int(live_or_scheduled_week)

    latest_any_week = (
        db.query(func.max(Matchup.week))
        .filter(Matchup.league_id == league.id, Matchup.season == league.season_year)
        .scalar()
    )
    if latest_any_week is not None:
        return int(latest_any_week)
    return None


def build_scoreboard_rows(db: Session, league: League, week: int | None = None) -> list[LeagueScoreboardRow]:
    selected_week = week if week is not None else resolve_default_matchup_week(db, league)
    if selected_week is None:
        return []

    home_team = db.query(Team).subquery()
    away_team = db.query(Team).subquery()
    rows = (
        db.query(
            Matchup,
            home_team.c.name,
            home_team.c.owner_user_id,
            away_team.c.name,
            away_team.c.owner_user_id,
        )
        .join(home_team, home_team.c.id == Matchup.home_team_id)
        .join(away_team, away_team.c.id == Matchup.away_team_id)
        .filter(
            Matchup.league_id == league.id,
            Matchup.season == league.season_year,
            Matchup.week == selected_week,
        )
        .order_by(Matchup.id.asc())
        .all()
    )
    owner_ids = {
        owner_user_id
        for _matchup, _home_name, home_owner_user_id, _away_name, away_owner_user_id in rows
        for owner_user_id in (home_owner_user_id, away_owner_user_id)
        if owner_user_id is not None
    }
    avatars_by_owner_id = {
        user_id: avatar_url
        for user_id, avatar_url in db.query(User.id, User.avatar_url).filter(User.id.in_(owner_ids)).all()
    } if owner_ids else {}

    return [
        LeagueScoreboardRow(
            matchup_id=matchup.id,
            week=matchup.week,
            status=matchup.status,
            home_team_id=matchup.home_team_id,
            home_team_name=home_name,
            home_owner_avatar_url=avatars_by_owner_id.get(home_owner_user_id),
            home_score=float(matchup.home_score or 0.0),
            away_team_id=matchup.away_team_id,
            away_team_name=away_name,
            away_owner_avatar_url=avatars_by_owner_id.get(away_owner_user_id),
            away_score=float(matchup.away_score or 0.0),
        )
        for matchup, home_name, home_owner_user_id, away_name, away_owner_user_id in rows
    ]


def build_power_rankings_rows(db: Session, league: League) -> list[LeaguePowerRankingRow]:
    standings = build_standings_summary(db, league)
    return [
        LeaguePowerRankingRow(
            team_id=row.team_id,
            team_name=row.team_name,
            rank=index,
            wins=int(row.wins or 0),
            losses=int(row.losses or 0),
            ties=int(row.ties or 0),
            points_for=float(row.points_for or 0.0),
        )
        for index, row in enumerate(standings, start=1)
    ]


def _transaction_headline(
    transaction_type: str,
    team_name: str,
    player_name: str | None,
    related_player_name: str | None,
) -> str:
    if transaction_type == "add":
        return f"{team_name} added {player_name or 'a player'}"
    if transaction_type == "drop":
        return f"{team_name} dropped {player_name or 'a player'}"
    if transaction_type == "add_drop":
        added = player_name or "a player"
        dropped = related_player_name or "a player"
        return f"{team_name} added {added} and dropped {dropped}"
    if transaction_type == "lineup":
        return f"{team_name} updated lineup for {player_name or 'a player'}"
    return f"{team_name} recorded {transaction_type.replace('_', ' ')}"


def _injury_headline(player_name: str, status_value: str, injury_text: str | None) -> str:
    if injury_text:
        return f"{player_name} — {status_value}: {injury_text}"
    return f"{player_name} — {status_value}"


def build_league_news_items(db: Session, league: League, limit: int = 25) -> list[LeagueNewsItem]:
    team_rows = db.query(Team).filter(Team.league_id == league.id).all()
    team_name_by_id = {row.id: row.name for row in team_rows}
    team_id_by_player_id = {
        player_id: team_id
        for player_id, team_id in db.query(RosterEntry.player_id, RosterEntry.team_id)
        .join(Team, Team.id == RosterEntry.team_id)
        .filter(Team.league_id == league.id)
        .all()
    }

    transactions = (
        db.query(Transaction)
        .filter(Transaction.league_id == league.id)
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
        .limit(limit)
        .all()
    )
    transaction_player_ids = {
        player_id
        for row in transactions
        for player_id in (row.player_id, row.related_player_id)
        if player_id is not None
    }
    player_name_by_id = {
        row.id: row.name
        for row in db.query(Player).filter(Player.id.in_(transaction_player_ids)).all()
    } if transaction_player_ids else {}

    transaction_items = [
        LeagueNewsItem(
            id=row.id,
            team_id=row.team_id,
            team_name=team_name_by_id.get(row.team_id),
            transaction_type=row.transaction_type,
            headline=_transaction_headline(
                row.transaction_type,
                team_name_by_id.get(row.team_id, "Team"),
                player_name_by_id.get(row.player_id or -1),
                player_name_by_id.get(row.related_player_id or -1),
            ),
            detail=row.reason,
            created_at=row.created_at,
        )
        for row in transactions
    ]

    roster_player_ids = list(team_id_by_player_id.keys())
    injury_items: list[LeagueNewsItem] = []
    if roster_player_ids:
        injury_rows = (
            db.query(Injury, Player)
            .join(Player, Player.id == Injury.player_id)
            .filter(
                Injury.player_id.in_(roster_player_ids),
                Injury.season == league.season_year,
            )
            .order_by(Injury.created_at.desc(), Injury.id.desc())
            .limit(limit)
            .all()
        )
        for injury, player in injury_rows:
            team_id = team_id_by_player_id.get(player.id)
            if team_id is None:
                continue
            detail_parts = []
            if injury.return_timeline:
                detail_parts.append(f"Return: {injury.return_timeline}")
            if injury.notes:
                detail_parts.append(injury.notes)
            injury_items.append(
                LeagueNewsItem(
                    id=1_000_000 + injury.id,
                    team_id=team_id,
                    team_name=team_name_by_id.get(team_id),
                    transaction_type="injury",
                    headline=_injury_headline(player.name, injury.status, injury.injury),
                    detail=" • ".join(detail_parts) if detail_parts else None,
                    created_at=injury.created_at,
                )
            )

    combined = sorted(
        [*transaction_items, *injury_items],
        key=lambda item: (item.created_at, item.id),
        reverse=True,
    )
    return combined[:limit]


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
        league=get_league_detail(db, league, viewer=current_user),
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
        matchup_summary=build_matchup_summary(db, league, owned_team, current_user),
        standings_summary=build_standings_summary(db, league),
        allowed_actions=build_allowed_actions(league, membership, owned_team),
    )
