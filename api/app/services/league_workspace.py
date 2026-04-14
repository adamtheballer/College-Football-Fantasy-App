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
    DraftRead,
    LeagueDetailRead,
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
        db.query(Matchup, home_team.c.name, away_team.c.name)
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
    return [
        LeagueScoreboardRow(
            matchup_id=matchup.id,
            week=matchup.week,
            status=matchup.status,
            home_team_id=matchup.home_team_id,
            home_team_name=home_name,
            home_score=float(matchup.home_score or 0.0),
            away_team_id=matchup.away_team_id,
            away_team_name=away_name,
            away_score=float(matchup.away_score or 0.0),
        )
        for matchup, home_name, away_name in rows
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
