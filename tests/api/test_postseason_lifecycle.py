"""Regression coverage for deterministic regular-season and playoff flow."""

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.postseason import (
    LeaguePostseasonSettings,
    PostseasonBracket,
    PostseasonFinalStanding,
    PostseasonMatchup,
)
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.services.postseason_service import (
    get_or_create_postseason_settings,
    progress_postseason,
    rank_regular_season_teams,
)


def _postseason_fixture(db_session, playoff_teams: int = 4):
    league = League(name=f"Postseason {playoff_teams}", season_year=2026, max_teams=playoff_teams, status="post_draft")
    db_session.add(league)
    db_session.flush()
    teams = [Team(league_id=league.id, name=f"Seed Candidate {index}") for index in range(1, playoff_teams + 1)]
    db_session.add_all(teams)
    db_session.flush()
    db_session.add(
        LeagueSettings(
            league_id=league.id,
            scoring_json={"ppr": 1},
            roster_slots_json={"QB": 1},
            playoff_teams=playoff_teams,
            waiver_type="faab",
            trade_review_type="commissioner",
        )
    )
    settings = LeaguePostseasonSettings(
        league_id=league.id,
        season=2026,
        regular_season_start_week=1,
        regular_season_end_week=1,
        playoff_start_week=2,
        championship_week=3,
        playoff_team_count=playoff_teams,
        championship_bracket_size=playoff_teams,
    )
    db_session.add(settings)
    db_session.flush()
    return league, teams, settings


def _add_regular_season_results(db_session, league, teams):
    """Seed an unambiguous regular-season order without using future weeks."""
    ordered = list(teams)
    pairs = [(ordered[index], ordered[-(index + 1)]) for index in range(len(ordered) // 2)]
    for index, (home, away) in enumerate(pairs):
        home_score = float(100 - (index * 10))
        away_score = float(10 + (index * 10))
        db_session.add(
            Matchup(
                league_id=league.id,
                season=2026,
                week=1,
                home_team_id=home.id,
                away_team_id=away.id,
                home_score=home_score,
                away_score=away_score,
                status="final",
            )
        )
    for index, team in enumerate(ordered):
        won = index < len(ordered) // 2
        db_session.add(
            Standing(
                league_id=league.id,
                team_id=team.id,
                season=2026,
                week=1,
                wins=1 if won else 0,
                losses=0 if won else 1,
                ties=0,
                points_for=float(100 - (index * 10)),
                points_against=float(10 + (index * 10)),
            )
        )
    db_session.flush()


def test_tied_regular_season_uses_complete_head_to_head_before_points_for(db_session):
    league, teams, settings = _postseason_fixture(db_session)
    # Team two beat team one head-to-head. Team one deliberately has more PF,
    # proving head-to-head is used before the PF fallback for a complete tie.
    db_session.add(
        Matchup(
            league_id=league.id,
            season=2026,
            week=1,
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            home_score=100.0,
            away_score=101.0,
            status="final",
        )
    )
    for team, wins, losses, points_for, points_against in (
        (teams[0], 1, 1, 250.0, 150.0),
        (teams[1], 1, 1, 200.0, 160.0),
        (teams[2], 0, 2, 150.0, 220.0),
        (teams[3], 0, 2, 100.0, 230.0),
    ):
        db_session.add(
            Standing(
                league_id=league.id,
                team_id=team.id,
                season=2026,
                week=1,
                wins=wins,
                losses=losses,
                ties=0,
                points_for=points_for,
                points_against=points_against,
            )
        )
    db_session.flush()

    ranked = rank_regular_season_teams(db_session, league, settings)

    assert [entry.team.id for entry in ranked[:2]] == [teams[1].id, teams[0].id]
    assert ranked[0].tiebreaker_explanation == "head_to_head"
    assert ranked[1].tiebreaker_explanation == "head_to_head"


def test_four_team_bracket_seeds_advances_ties_and_finalizes_complete_season_table(db_session):
    league, teams, _settings = _postseason_fixture(db_session)
    _add_regular_season_results(db_session, league, teams)

    created = progress_postseason(db_session, league, 2026, 1)
    bracket = db_session.query(PostseasonBracket).filter_by(league_id=league.id, season=2026).one()
    semifinals = (
        db_session.query(PostseasonMatchup)
        .filter_by(bracket_id=bracket.id)
        .order_by(PostseasonMatchup.slot_number.asc())
        .all()
    )

    assert created.bracket_created is True
    assert len(semifinals) == 2
    assert [(row.team_a_seed, row.team_b_seed) for row in semifinals] == [(1, 4), (2, 3)]

    first_semifinal = db_session.get(Matchup, semifinals[0].fantasy_matchup_id)
    second_semifinal = db_session.get(Matchup, semifinals[1].fantasy_matchup_id)
    first_semifinal.home_score = first_semifinal.away_score = 55.0
    first_semifinal.status = "final"
    second_semifinal.home_score = 40.0
    second_semifinal.away_score = 60.0
    second_semifinal.status = "final"
    db_session.flush()

    advanced = progress_postseason(db_session, league, 2026, 2)
    championship_row = (
        db_session.query(PostseasonMatchup)
        .filter(PostseasonMatchup.bracket_id == bracket.id, PostseasonMatchup.round_id != semifinals[0].round_id)
        .one()
    )
    championship = db_session.get(Matchup, championship_row.fantasy_matchup_id)

    assert advanced.matchups_finalized == 2
    assert advanced.matchups_created == 1
    assert semifinals[0].advancing_team_id == semifinals[0].team_a_id
    assert semifinals[0].tiebreaker_used == "higher_seed"

    championship.home_score = 80.0
    championship.away_score = 70.0
    championship.status = "final"
    db_session.flush()
    finalized = progress_postseason(db_session, league, 2026, 3)

    assert finalized.bracket_completed is True
    assert bracket.status == "COMPLETED"
    final_table = (
        db_session.query(PostseasonFinalStanding)
        .filter_by(league_id=league.id, season=2026)
        .order_by(PostseasonFinalStanding.final_place.asc())
        .all()
    )
    assert len(final_table) == 4
    assert final_table[0].postseason_result == "CHAMPION"
    assert [row.final_place for row in final_table] == [1, 2, 3, 4]
    assert all(row.points_for > 0 for row in final_table)

    # Re-running a completed week cannot create a second bracket or matchup.
    rerun = progress_postseason(db_session, league, 2026, 3)
    assert rerun.matchups_created == 0
    assert db_session.query(PostseasonBracket).filter_by(league_id=league.id, season=2026).count() == 1
    assert db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id).count() == 3


def test_six_team_bracket_gives_top_two_seeds_byes_and_reseeds_semifinals(db_session):
    league, teams, _settings = _postseason_fixture(db_session, playoff_teams=6)
    _add_regular_season_results(db_session, league, teams)

    progress_postseason(db_session, league, 2026, 1)
    bracket = db_session.query(PostseasonBracket).filter_by(league_id=league.id, season=2026).one()
    opening_matchups = db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id).all()
    assert [(row.team_a_seed, row.team_b_seed) for row in opening_matchups] == [(3, 6), (4, 5)]

    for row in opening_matchups:
        matchup = db_session.get(Matchup, row.fantasy_matchup_id)
        matchup.home_score = 70.0
        matchup.away_score = 40.0
        matchup.status = "final"
    db_session.flush()

    progress_postseason(db_session, league, 2026, 2)
    semifinal_pairs = [
        (row.team_a_seed, row.team_b_seed)
        for row in db_session.query(PostseasonMatchup)
        .filter(PostseasonMatchup.bracket_id == bracket.id, PostseasonMatchup.round_id != opening_matchups[0].round_id)
        .order_by(PostseasonMatchup.slot_number.asc())
        .all()
    ]
    assert semifinal_pairs == [(1, 4), (2, 3)]


def test_two_team_bracket_uses_a_single_championship_matchup(db_session):
    league, teams, _settings = _postseason_fixture(db_session, playoff_teams=2)
    _add_regular_season_results(db_session, league, teams)

    created = progress_postseason(db_session, league, 2026, 1)
    bracket = db_session.query(PostseasonBracket).filter_by(league_id=league.id, season=2026).one()
    matchup = db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id).one()

    assert created.bracket_created is True
    assert matchup.team_a_seed == 1
    assert matchup.team_b_seed == 2


def test_bracket_waits_until_the_regular_season_is_complete(db_session):
    league, teams, settings = _postseason_fixture(db_session)
    _add_regular_season_results(db_session, league, teams)
    settings.regular_season_end_week = 2
    db_session.flush()

    early = progress_postseason(db_session, league, 2026, 2)

    assert early.bracket_created is False
    assert db_session.query(PostseasonBracket).filter_by(league_id=league.id, season=2026).count() == 0


def test_settings_normalizes_default_playoff_count_to_actual_eligible_league_size(db_session):
    league = League(name="Two team default", season_year=2026, max_teams=2, status="post_draft")
    db_session.add(league)
    db_session.flush()
    db_session.add_all([Team(league_id=league.id, name="One"), Team(league_id=league.id, name="Two")])
    db_session.add(
        LeagueSettings(
            league_id=league.id,
            scoring_json={"ppr": 1},
            roster_slots_json={"QB": 1},
            playoff_teams=4,
            waiver_type="faab",
            trade_review_type="commissioner",
        )
    )
    db_session.flush()

    settings = get_or_create_postseason_settings(db_session, league)

    assert settings.playoff_team_count == 2
    assert settings.championship_bracket_size == 2
