from datetime import datetime, timezone

from collegefootballfantasy_api.app.models.draft import Draft
from collegefootballfantasy_api.app.models.draft_pick import DraftPick
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_projection import WeeklyProjection
from collegefootballfantasy_api.app.services.league_roster_matchup import (
    build_settings_view,
    build_matchup_tab_view,
    build_roster_tab_view,
)


def _user(db_session, suffix: str) -> User:
    user = User(
        email=f"league-projection-{suffix}@example.com",
        first_name=f"Projection{suffix}",
        password_hash="hash",
        api_token=f"projection-token-{suffix}",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _players_and_projections(db_session) -> tuple[Player, Player]:
    receiver = Player(name="Projected Receiver", position="WR", school="Test State", external_id="wr-1")
    opponent = Player(name="Projected Opponent", position="RB", school="Test State", external_id="rb-1")
    db_session.add_all([receiver, opponent])
    db_session.flush()
    db_session.add_all(
        [
            WeeklyProjection(
                player_id=receiver.id,
                season=2026,
                week=1,
                pass_attempts=0.0,
                rush_attempts=0.0,
                targets=8.0,
                receptions=5.0,
                expected_plays=8.0,
                expected_rush_per_play=0.0,
                expected_td_per_play=0.125,
                pass_yards=0.0,
                rush_yards=0.0,
                rec_yards=75.0,
                pass_tds=0.0,
                rush_tds=0.0,
                rec_tds=1.0,
                interceptions=0.0,
                fantasy_points=18.5,
                floor=9.25,
                ceiling=27.75,
                boom_prob=0.2,
                bust_prob=0.1,
            ),
            WeeklyProjection(
                player_id=opponent.id,
                season=2026,
                week=1,
                pass_attempts=0.0,
                rush_attempts=14.0,
                targets=0.0,
                receptions=0.0,
                expected_plays=14.0,
                expected_rush_per_play=1.0,
                expected_td_per_play=0.0,
                pass_yards=0.0,
                rush_yards=140.0,
                rec_yards=0.0,
                pass_tds=0.0,
                rush_tds=0.0,
                rec_tds=0.0,
                interceptions=0.0,
                fantasy_points=14.0,
                floor=7.0,
                ceiling=21.0,
                boom_prob=0.2,
                bust_prob=0.1,
            ),
        ]
    )
    db_session.flush()
    return receiver, opponent


def _league_with_matchup(
    db_session,
    user: User,
    receiver: Player,
    opponent_player: Player,
    name: str,
    scoring_json: dict,
) -> League:
    league = League(name=name, season_year=2026, max_teams=2, status="post_draft", commissioner_user_id=user.id)
    db_session.add(league)
    db_session.flush()
    settings = LeagueSettings(
        league_id=league.id,
        scoring_json=scoring_json,
        roster_slots_json={"WR": 1, "RB": 1, "BENCH": 1, "IR": 1},
        playoff_teams=2,
        waiver_type="faab",
        trade_review_type="commissioner",
    )
    user_team = Team(league_id=league.id, name=f"{name} User", owner_user_id=user.id, owner_name=user.first_name)
    opponent_team = Team(league_id=league.id, name=f"{name} Opponent", owner_user_id=None, owner_name="Opponent")
    db_session.add_all([settings, user_team, opponent_team])
    db_session.flush()
    db_session.add_all(
        [
            RosterEntry(
                league_id=league.id,
                team_id=user_team.id,
                player_id=receiver.id,
                slot="WR",
                status="active",
            ),
            RosterEntry(
                league_id=league.id,
                team_id=opponent_team.id,
                player_id=opponent_player.id,
                slot="RB",
                status="active",
            ),
            Matchup(
                league_id=league.id,
                season=2026,
                week=1,
                home_team_id=user_team.id,
                away_team_id=opponent_team.id,
                status="scheduled",
            ),
        ]
    )
    db_session.commit()
    return league


def test_roster_projected_points_use_league_scoring_for_ppr_and_standard(client, db_session):
    user = _user(db_session, "owner")
    receiver, opponent = _players_and_projections(db_session)
    ppr_league = _league_with_matchup(db_session, user, receiver, opponent, "PPR League", {"ppr": 1})
    standard_league = _league_with_matchup(db_session, user, receiver, opponent, "Standard League", {"ppr": 0})

    ppr_roster = build_roster_tab_view(db_session, ppr_league, user, selected_week=1)
    standard_roster = build_roster_tab_view(db_session, standard_league, user, selected_week=1)

    assert ppr_roster.roster[0].projected_points == 18.5
    assert ppr_roster.roster[0].weekly_projected_fantasy_points == 18.5
    assert standard_roster.roster[0].projected_points == 13.5
    assert standard_roster.roster[0].weekly_projected_fantasy_points == 13.5
    assert ppr_roster.roster[0].floor != standard_roster.roster[0].floor
    assert ppr_roster.roster[0].ceiling != standard_roster.roster[0].ceiling


def test_pre_draft_roster_view_hides_stale_roster_entries(client, db_session):
    user = _user(db_session, "pre-draft-owner")
    receiver, _opponent = _players_and_projections(db_session)
    league = League(name="Pre Draft League", season_year=2026, max_teams=2, status="active", commissioner_user_id=user.id)
    db_session.add(league)
    db_session.flush()
    settings = LeagueSettings(
        league_id=league.id,
        scoring_json={"ppr": 1},
        roster_slots_json={"WR": 1, "BENCH": 1, "IR": 1},
        playoff_teams=2,
        waiver_type="faab",
        trade_review_type="commissioner",
    )
    team = Team(league_id=league.id, name="Pre Draft User", owner_user_id=user.id, owner_name=user.first_name)
    db_session.add_all([settings, team])
    db_session.flush()
    draft = Draft(
        league_id=league.id,
        draft_datetime_utc=datetime(2026, 8, 1, tzinfo=timezone.utc),
        timezone="UTC",
        draft_type="snake",
        pick_timer_seconds=90,
        status="scheduled",
    )
    stale_entry = RosterEntry(
        league_id=league.id,
        team_id=team.id,
        player_id=receiver.id,
        slot="WR",
        status="active",
    )
    db_session.add_all([draft, stale_entry])
    db_session.flush()
    db_session.add(
        DraftPick(
            draft_id=draft.id,
            team_id=team.id,
            player_id=receiver.id,
            overall_pick=1,
            round_number=1,
            round_pick=1,
        )
    )
    db_session.commit()

    roster_view = build_roster_tab_view(db_session, league, user, selected_week=1)
    settings_view = build_settings_view(db_session, league, user)

    assert roster_view.roster == []
    assert roster_view.data == []
    assert roster_view.message == "No players on this roster yet. Complete the draft to populate your roster."
    assert settings_view.rosters == []
    assert settings_view.draft_results == []


def test_matchup_projected_totals_and_win_probability_use_league_scoring(client, db_session):
    user = _user(db_session, "matchup-owner")
    receiver, opponent = _players_and_projections(db_session)
    ppr_league = _league_with_matchup(db_session, user, receiver, opponent, "PPR Matchup", {"ppr": 1})
    standard_league = _league_with_matchup(db_session, user, receiver, opponent, "Standard Matchup", {"ppr": 0})

    ppr_matchup = build_matchup_tab_view(db_session, ppr_league, user, selected_week=1)
    standard_matchup = build_matchup_tab_view(db_session, standard_league, user, selected_week=1)

    assert ppr_matchup.my_team is not None
    assert ppr_matchup.opponent_team is not None
    assert standard_matchup.my_team is not None
    assert standard_matchup.opponent_team is not None
    assert ppr_matchup.my_team.projected_total == 18.5
    assert standard_matchup.my_team.projected_total == 13.5
    assert ppr_matchup.opponent_team.projected_total == 14.0
    assert standard_matchup.opponent_team.projected_total == 14.0
    assert ppr_matchup.my_team.win_probability > 50.0
    assert standard_matchup.my_team.win_probability < 50.0
