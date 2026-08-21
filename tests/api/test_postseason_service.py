from datetime import datetime, timezone

import pytest

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.postseason import LeaguePostseasonSettings, PostseasonBracket, PostseasonEntry, PostseasonFinalStanding, PostseasonMatchup
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.api.routes.insights import _championships_by_user
from collegefootballfantasy_api.app.schemas.postseason import PostseasonBracketRead
from collegefootballfantasy_api.app.services.postseason_service import (
    calculate_final_standings,
    advance_postseason_state,
    lock_postseason_seeds,
    materialize_ready_postseason_matchups,
    postseason_calendar,
    refresh_postseason_activity,
    resolve_postseason_matchup,
    serialize_postseason,
)
def test_lifecycle_skips_only_leagues_when_the_sealed_calendar_is_unavailable(monkeypatch, db_session):
    league = League(name="Calendar blocked", season_year=2026, max_teams=2, status="post_draft")
    db_session.add(league); db_session.flush()
    db_session.add(LeagueSettings(
        league_id=league.id, playoff_teams=2, scoring_json={}, roster_slots_json={}, waiver_type="faab",
        trade_review_type="none", superflex_enabled=False, kicker_enabled=True, defense_enabled=False,
    ))
    db_session.commit()

    from collegefootballfantasy_api.app.services.season_calendar import SeasonCalendarCoverageError
    import collegefootballfantasy_api.app.services.postseason_service as postseason_service

    def unavailable(*_args, **_kwargs):
        raise SeasonCalendarCoverageError("sealed 2026 schedule snapshot is unavailable; calendar certification is blocked")

    monkeypatch.setattr(postseason_service, "calendar_for_season", unavailable)

    assert advance_postseason_state(db_session)["calendar_blocked"] == 1


def test_postseason_calendar_delegates_to_the_certified_calendar(monkeypatch, db_session):
    expected_regular_weeks = {2: 12, 4: 11, 6: 10, 8: 10}
    from collegefootballfantasy_api.app.services.season_calendar import CertifiedSeasonCalendar

    def fixture_calendar(season, team_count):
        rounds = {2: 1, 4: 2, 6: 3, 8: 3}[team_count]
        championship = 13
        start = championship - rounds + 1
        return CertifiedSeasonCalendar(
            season=season, playoff_team_count=team_count, regular_season_start_week=1,
            regular_season_end_week=start - 1, playoff_start_week=start, championship_week=championship,
            max_rounds=rounds, calendar_policy_version="test", source_identity="test", source_revision="test",
            source_sha256="0" * 64, source_format_version="test",
        )

    import collegefootballfantasy_api.app.services.postseason_service as postseason_service

    monkeypatch.setattr(postseason_service, "calendar_for_season", fixture_calendar)
    for playoff_teams, expected_regular_end in expected_regular_weeks.items():
        league = League(name=f"Calendar {playoff_teams}", season_year=2026, max_teams=playoff_teams)
        calendar = postseason_calendar(db_session, league, playoff_teams)
        assert calendar["regular_season_end_week"] == expected_regular_end
        assert calendar["championship_week"] == 13


def _four_team_league(db_session):
    league = League(name="Postseason", season_year=2026, max_teams=4, status="post_draft")
    db_session.add(league); db_session.flush()
    db_session.add(LeagueSettings(league_id=league.id, playoff_teams=4, scoring_json={}, roster_slots_json={}, waiver_type="faab", trade_review_type="none", superflex_enabled=False, kicker_enabled=True, defense_enabled=False))
    teams = [Team(league_id=league.id, name=f"Team {index}") for index in range(1, 5)]
    db_session.add_all(teams); db_session.flush()
    db_session.add(LeaguePostseasonSettings(league_id=league.id, season=2026, regular_season_start_week=1, regular_season_end_week=1, playoff_start_week=2, championship_week=3, playoff_team_count=4, championship_bracket_size=4, reseeding_enabled=False))
    # Team 1 through Team 4 finish in the deterministic order shown.
    db_session.add_all([
        Matchup(league_id=league.id, season=2026, week=1, home_team_id=teams[0].id, away_team_id=teams[3].id, home_score=120, away_score=90, status="final"),
        Matchup(league_id=league.id, season=2026, week=1, home_team_id=teams[1].id, away_team_id=teams[2].id, home_score=110, away_score=100, status="final"),
    ])
    db_session.commit()
    return league, teams


def _node(db_session, bracket, matchup_type):
    return db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id, matchup_type=matchup_type).one()


def test_four_team_bracket_routes_canonical_results_and_generates_all_final_places(db_session):
    league, teams = _four_team_league(db_session)
    bracket = lock_postseason_seeds(db_session, league)
    db_session.commit()
    assert bracket.total_teams == 4
    semifinals = db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id, matchup_type="SEMIFINAL").all()
    assert len(semifinals) == 2
    assert all(node.fantasy_matchup_id for node in semifinals)

    for node in semifinals:
        matchup = db_session.get(Matchup, node.fantasy_matchup_id)
        matchup.home_score, matchup.away_score, matchup.status = 101, 100, "final"
        assert resolve_postseason_matchup(db_session, node)
    assert materialize_ready_postseason_matchups(db_session, bracket) == 2
    db_session.commit()

    for matchup_type in ("CHAMPIONSHIP", "THIRD_PLACE"):
        node = _node(db_session, bracket, matchup_type)
        matchup = db_session.get(Matchup, node.fantasy_matchup_id)
        matchup.home_score, matchup.away_score, matchup.status = 99, 98, "final"
        assert resolve_postseason_matchup(db_session, node)
    final_rows = calculate_final_standings(db_session, bracket)
    db_session.commit()

    assert [row.final_place for row in final_rows] == [1, 2, 3, 4]
    assert db_session.query(PostseasonFinalStanding).filter_by(bracket_id=bracket.id).count() == 4
    assert bracket.status == "COMPLETED"
    contract = PostseasonBracketRead.model_validate(serialize_postseason(db_session, league))
    assert contract.champion is not None
    assert len(contract.final_standings) == 4


def test_exact_playoff_tie_advances_higher_original_seed(db_session):
    league, _teams = _four_team_league(db_session)
    bracket = lock_postseason_seeds(db_session, league)
    semi = db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id, matchup_type="SEMIFINAL").order_by(PostseasonMatchup.id).first()
    matchup = db_session.get(Matchup, semi.fantasy_matchup_id)
    matchup.home_score = matchup.away_score = 100
    matchup.status = "final"
    assert resolve_postseason_matchup(db_session, semi)
    assert semi.tiebreaker_used == "HIGHER_SEED_V1"
    assert semi.winner_team_id == (semi.team_a_id if semi.team_a_seed < semi.team_b_seed else semi.team_b_id)


def _playoff_league(db_session, *, team_count: int):
    league = League(name=f"{team_count}-team playoffs", season_year=2026, max_teams=team_count, status="post_draft")
    db_session.add(league); db_session.flush()
    db_session.add(LeagueSettings(
        league_id=league.id, playoff_teams=team_count, scoring_json={}, roster_slots_json={}, waiver_type="faab",
        trade_review_type="none", superflex_enabled=False, kicker_enabled=True, defense_enabled=False,
    ))
    teams = [Team(league_id=league.id, name=f"Team {index}") for index in range(1, team_count + 1)]
    db_session.add_all(teams); db_session.flush()
    rounds = 1 if team_count == 2 else (2 if team_count == 4 else 3)
    db_session.add(LeaguePostseasonSettings(
        league_id=league.id, season=2026, regular_season_start_week=1, regular_season_end_week=1,
        playoff_start_week=2, championship_week=rounds + 1, playoff_team_count=team_count,
        championship_bracket_size=team_count, reseeding_enabled=False,
    ))
    # All regular matchups are final. The deterministic ranker then yields a
    # stable, auditable order even where teams share a record.
    for index in range(team_count // 2):
        db_session.add(Matchup(
            league_id=league.id, season=2026, week=1,
            home_team_id=teams[index].id, away_team_id=teams[-(index + 1)].id,
            home_score=100 - index, away_score=90 - index, status="final",
        ))
    db_session.commit()
    return league


def _finish_fixed_bracket(db_session, bracket):
    for round_number in range(1, bracket.max_rounds + 1):
        for node in db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id).all():
            if node.fantasy_matchup_id is None:
                continue
            matchup = db_session.get(Matchup, node.fantasy_matchup_id)
            if node.status == "FINAL" or matchup.status == "final":
                continue
            matchup.home_score, matchup.away_score, matchup.status = 100, 90, "final"
            assert resolve_postseason_matchup(db_session, node)
        materialize_ready_postseason_matchups(db_session, bracket)


def test_two_six_and_eight_team_formats_materialize_only_canonical_games_and_finish_all_places(db_session):
    for team_count in (2, 6, 8):
        league = _playoff_league(db_session, team_count=team_count)
        bracket = lock_postseason_seeds(db_session, league)
        assert bracket.first_kickoff_at is None
        _finish_fixed_bracket(db_session, bracket)
        final_rows = calculate_final_standings(db_session, bracket)
        assert [row.final_place for row in final_rows] == list(range(1, team_count + 1))
        assert any(row.wins > 0 for row in final_rows)
        assert all(node.fantasy_matchup_id for node in db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id))


@pytest.mark.parametrize("playoff_team_count", [2, 4, 6, 8])
def test_fourteen_team_league_seeds_each_supported_playoff_bracket(playoff_team_count, db_session):
    league = League(name=f"14-team {playoff_team_count}-playoff league", season_year=2026, max_teams=14, status="post_draft")
    db_session.add(league); db_session.flush()
    db_session.add(LeagueSettings(
        league_id=league.id, playoff_teams=playoff_team_count, scoring_json={}, roster_slots_json={}, waiver_type="faab",
        trade_review_type="none", superflex_enabled=False, kicker_enabled=True, defense_enabled=False,
    ))
    teams = [Team(league_id=league.id, name=f"Team {index}") for index in range(1, 15)]
    db_session.add_all(teams); db_session.flush()
    rounds = {2: 1, 4: 2, 6: 3, 8: 3}[playoff_team_count]
    db_session.add(LeaguePostseasonSettings(
        league_id=league.id, season=2026, regular_season_start_week=1, regular_season_end_week=1,
        playoff_start_week=2, championship_week=rounds + 1, playoff_team_count=playoff_team_count,
        championship_bracket_size=playoff_team_count, reseeding_enabled=False,
    ))
    for index in range(7):
        db_session.add(Matchup(
            league_id=league.id, season=2026, week=1, home_team_id=teams[index].id, away_team_id=teams[-(index + 1)].id,
            home_score=200 - index, away_score=100 - index, status="final",
        ))
    db_session.commit()

    bracket = lock_postseason_seeds(db_session, league)
    entries = db_session.query(PostseasonEntry).filter_by(bracket_id=bracket.id).order_by(PostseasonEntry.bracket_seed).all()
    assert bracket.total_teams == playoff_team_count
    assert [entry.bracket_seed for entry in entries] == list(range(1, playoff_team_count + 1))
    assert [entry.regular_season_rank for entry in entries] == list(range(1, playoff_team_count + 1))


def test_bracket_does_not_activate_until_a_linked_canonical_game_starts(db_session):
    league, _teams = _four_team_league(db_session)
    bracket = lock_postseason_seeds(db_session, league)
    assert bracket.status == "LOCKED"
    assert bracket.first_kickoff_at is None
    semifinal = db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id, matchup_type="SEMIFINAL").first()
    db_session.get(Matchup, semifinal.fantasy_matchup_id).status = "live"
    assert refresh_postseason_activity(db_session, bracket)
    assert bracket.status == "ACTIVE"
    assert bracket.first_kickoff_at is not None


def test_correction_after_dependent_playoff_game_started_requires_review(db_session):
    league, _teams = _four_team_league(db_session)
    bracket = lock_postseason_seeds(db_session, league)
    semifinals = db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id, matchup_type="SEMIFINAL").all()
    semifinal = semifinals[0]
    original = db_session.get(Matchup, semifinal.fantasy_matchup_id)
    original.home_score, original.away_score, original.status = 101, 100, "final"
    assert resolve_postseason_matchup(db_session, semifinal)
    other = db_session.get(Matchup, semifinals[1].fantasy_matchup_id)
    other.home_score, other.away_score, other.status = 101, 100, "final"
    assert resolve_postseason_matchup(db_session, semifinals[1])
    materialize_ready_postseason_matchups(db_session, bracket)
    championship = _node(db_session, bracket, "CHAMPIONSHIP")
    db_session.get(Matchup, championship.fantasy_matchup_id).status = "live"
    db_session.flush()
    assert championship.id in {semifinal.next_winner_matchup_id, semifinal.next_loser_matchup_id}
    if original.home_team_id == semifinal.winner_team_id:
        original.home_score, original.away_score = 100, 101
        corrected_winner = original.away_team_id
    else:
        original.home_score, original.away_score = 101, 100
        corrected_winner = original.home_team_id
    assert corrected_winner != semifinal.winner_team_id
    score_for_a = original.home_score if original.home_team_id == semifinal.team_a_id else original.away_score
    score_for_b = original.away_score if original.home_team_id == semifinal.team_a_id else original.home_score
    assert (semifinal.team_a_id if score_for_a > score_for_b else semifinal.team_b_id) == corrected_winner
    assert not resolve_postseason_matchup(db_session, semifinal)
    assert bracket.status == "REVIEW_REQUIRED"


def test_one_league_can_retain_multiple_season_brackets(db_session):
    league, _teams = _four_team_league(db_session)
    db_session.add(PostseasonBracket(
        league_id=league.id, season=2025, bracket_type="CHAMPIONSHIP", status="COMPLETED",
        total_teams=4, total_rounds=2,
    ))
    db_session.add(PostseasonBracket(
        league_id=league.id, season=2026, bracket_type="CHAMPIONSHIP", status="PLANNED",
        total_teams=4, total_rounds=2,
    ))
    db_session.commit()
    assert db_session.query(PostseasonBracket).filter_by(league_id=league.id).count() == 2


def test_completed_championship_correction_recalculates_final_standings(db_session):
    league = _playoff_league(db_session, team_count=2)
    bracket = lock_postseason_seeds(db_session, league)
    championship = _node(db_session, bracket, "CHAMPIONSHIP")
    matchup = db_session.get(Matchup, championship.fantasy_matchup_id)
    matchup.home_score, matchup.away_score, matchup.status = 101, 100, "final"
    assert resolve_postseason_matchup(db_session, championship)
    initial = calculate_final_standings(db_session, bracket)
    initial_champion = initial[0].team_id
    if matchup.home_team_id == initial_champion:
        matchup.home_score, matchup.away_score = 100, 101
    else:
        matchup.home_score, matchup.away_score = 101, 100
    advance_postseason_state(db_session)
    corrected = db_session.query(PostseasonFinalStanding).filter_by(bracket_id=bracket.id).order_by(PostseasonFinalStanding.final_place).all()
    assert corrected[0].team_id != initial_champion
    assert bracket.status == "COMPLETED"


def test_career_championships_use_finalized_postseason_placement_not_cumulative_points(db_session):
    league = League(name="Career championship source", season_year=2026, max_teams=2)
    winner = User(email="winner@example.com", first_name="Winner", password_hash="x", api_token="career-winner")
    points_leader = User(email="points@example.com", first_name="Points", password_hash="x", api_token="career-points")
    db_session.add_all([league, winner, points_leader]); db_session.flush()
    winner_team = Team(league_id=league.id, name="Winner Team", owner_user_id=winner.id)
    points_team = Team(league_id=league.id, name="Points Team", owner_user_id=points_leader.id)
    db_session.add_all([winner_team, points_team]); db_session.flush()
    bracket = PostseasonBracket(league_id=league.id, season=2026, bracket_type="CHAMPIONSHIP", status="COMPLETED", total_teams=2, total_rounds=1)
    db_session.add(bracket); db_session.flush()
    db_session.add_all([
        PostseasonFinalStanding(bracket_id=bracket.id, league_id=league.id, season=2026, team_id=winner_team.id, final_place=1, regular_season_rank=2, postseason_result="CHAMPIONSHIP", finalized_at=datetime.now(timezone.utc)),
        PostseasonFinalStanding(bracket_id=bracket.id, league_id=league.id, season=2026, team_id=points_team.id, final_place=2, regular_season_rank=1, postseason_result="CHAMPIONSHIP", finalized_at=datetime.now(timezone.utc)),
    ])
    db_session.commit()
    assert _championships_by_user(db_session) == {winner.id: 1}
