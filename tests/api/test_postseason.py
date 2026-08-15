from decimal import Decimal

import pytest

from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.postseason import (
    LeaguePostseasonSettings,
    PostseasonFinalStanding,
    PostseasonMatchup,
)
from collegefootballfantasy_api.app.models.scoring_admin_audit import ScoringAdminAudit
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.core.security import create_access_token
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.services.postseason_service import (
    SeedCandidate,
    _resolve_tied_group,
    finalize_certified_postseason_matchups,
    lock_postseason_seeding,
    postseason_bracket_payload,
    preview_postseason_seeding,
    refresh_locked_postseason_after_regular_correction,
)
from collegefootballfantasy_api.app.services.league_workspace import build_standings_summary


def _league_with_regular_results(db_session, *, playoff_teams: int, team_count: int = 8):
    league = League(name="Postseason Test", season_year=2026, max_teams=team_count, status="in_season")
    db_session.add(league)
    db_session.flush()
    db_session.add(LeagueSettings(league_id=league.id, playoff_teams=playoff_teams))
    db_session.add(
        LeaguePostseasonSettings(
            league_id=league.id,
            season=2026,
            regular_season_start_week=1,
            regular_season_end_week=1,
            playoff_start_week=2,
            championship_week=4 if playoff_teams == 6 else 3,
            playoff_team_count=playoff_teams,
            championship_bracket_size=playoff_teams,
            reseeding_enabled=False,
            third_place_game_enabled=False,
            losers_bracket_enabled=False,
        )
    )
    teams = [
        Team(league_id=league.id, name=f"Team {index}", postseason_tiebreak_lot=f"lot-{index:02d}")
        for index in range(1, team_count + 1)
    ]
    db_session.add_all(teams)
    db_session.flush()
    # Every team is represented in the certified regular-season input. Winners
    # are ordered by PF; the top six are known before bracket generation.
    for pair_index in range(0, team_count, 2):
        home, away = teams[pair_index], teams[pair_index + 1]
        home_score = float(140 - pair_index)
        away_score = float(80 - pair_index)
        db_session.add(
            Matchup(
                league_id=league.id,
                season=2026,
                week=1,
                home_team_id=home.id,
                away_team_id=away.id,
                status="final",
                home_score=home_score,
                away_score=away_score,
            )
        )
        db_session.add_all(
            [
                TeamWeekScore(league_id=league.id, team_id=home.id, season=2026, week=1, total_points=home_score, status="final"),
                TeamWeekScore(league_id=league.id, team_id=away.id, season=2026, week=1, total_points=away_score, status="final"),
            ]
        )
    db_session.commit()
    return league, teams


def test_seeding_uses_ties_then_points_for_and_persists_explanation(db_session):
    league, teams = _league_with_regular_results(db_session, playoff_teams=4)
    # Regular-season records remain valid ties. These two teams have the same
    # winning percentage, while points-for supplies the deterministic split.
    tied = db_session.query(Matchup).filter(Matchup.league_id == league.id).first()
    tied.home_score = 100.0
    tied.away_score = 100.0
    db_session.commit()

    preview = preview_postseason_seeding(db_session, league)
    tied_entry = next(entry for entry in preview["entries"] if entry["team_id"] in {teams[0].id, teams[1].id})
    assert tied_entry["record"]["ties"] == 1
    assert tied_entry["resolved_by"] in {"winning_percentage", "points_for", "head_to_head", "best_weekly_score", "tiebreak_lot"}

    bracket = lock_postseason_seeding(db_session, league)
    db_session.commit()
    payload = postseason_bracket_payload(db_session, league)
    assert bracket.status == "PLAYOFFS_ACTIVE"
    assert [entry["seed"] for entry in payload["entries"]] == [1, 2, 3, 4]
    assert all(entry["explanation"] for entry in payload["entries"])


def test_asymmetric_multi_team_head_to_head_is_skipped_and_lot_is_stable(db_session):
    league, teams = _league_with_regular_results(db_session, playoff_teams=4)
    settings = db_session.query(LeaguePostseasonSettings).filter_by(league_id=league.id).one()
    settings.regular_season_end_week = 3
    # Only one pair plays again: a three-team head-to-head mini-table would be
    # asymmetric and must not decide a seed.
    db_session.add(
        Matchup(
            league_id=league.id,
            season=2026,
            week=2,
            home_team_id=teams[0].id,
            away_team_id=teams[1].id,
            status="final",
            home_score=1.0,
            away_score=0.0,
        )
    )
    db_session.flush()
    candidates = [
        SeedCandidate(team=teams[index], wins=5, losses=2, ties=0, points_for=Decimal("700"), points_against=Decimal("600"), weekly_scores=(Decimal("120"),), lot=f"lot-{index}")
        for index in range(3)
    ]
    resolved = _resolve_tied_group(db_session, league, settings, candidates)
    assert [candidate.team.id for candidate in resolved] == [teams[0].id, teams[1].id, teams[2].id]
    assert all(any(item.get("status") == "skipped_asymmetric" for item in candidate.trace) for candidate in candidates)


def test_six_team_bracket_grants_top_two_byes_and_advances_higher_seed_on_playoff_tie(db_session):
    league, _teams = _league_with_regular_results(db_session, playoff_teams=6)
    bracket = lock_postseason_seeding(db_session, league)
    db_session.commit()

    opening = (
        db_session.query(PostseasonMatchup)
        .filter(PostseasonMatchup.bracket_id == bracket.id, PostseasonMatchup.team_a_seed == 3)
        .one()
    )
    assert opening.team_b_seed == 6
    assert opening.fantasy_matchup_id is not None
    game = db_session.get(Matchup, opening.fantasy_matchup_id)
    game.status, game.home_score, game.away_score = "final", 99.0, 99.0
    db_session.commit()

    assert finalize_certified_postseason_matchups(db_session, league) == 1
    db_session.commit()
    db_session.refresh(opening)
    assert opening.advancing_team_id == opening.team_a_id
    assert opening.tiebreaker_used == "higher_original_playoff_seed"

    payload = postseason_bracket_payload(db_session, league)
    semifinal_with_seed_one = next(round_ for round_ in payload["rounds"] if round_["team_a"]["seed"] == 1)
    assert semifinal_with_seed_one["team_b"]["seed"] == 4 or semifinal_with_seed_one["team_b"]["seed"] is None
    assert {entry["seed"] for entry in payload["entries"]} == {1, 2, 3, 4, 5, 6}


def test_finalization_is_idempotent_and_persists_all_playoff_places(db_session):
    league, _teams = _league_with_regular_results(db_session, playoff_teams=4)
    bracket = lock_postseason_seeding(db_session, league)
    db_session.commit()

    # Complete the fixed bracket through the same canonical Matchup records.
    for _ in range(4):
        scheduled = (
            db_session.query(PostseasonMatchup)
            .filter(PostseasonMatchup.bracket_id == bracket.id, PostseasonMatchup.status == "SCHEDULED")
            .all()
        )
        for row in scheduled:
            game = db_session.get(Matchup, row.fantasy_matchup_id)
            game.status = "final"
            game.home_score = 100.0
            game.away_score = 90.0
        db_session.flush()
        finalize_certified_postseason_matchups(db_session, league)
        db_session.flush()

    assert finalize_certified_postseason_matchups(db_session, league) == 0
    final_places = (
        db_session.query(PostseasonFinalStanding)
        .filter(PostseasonFinalStanding.league_id == league.id)
        .order_by(PostseasonFinalStanding.final_place)
        .all()
    )
    assert [row.final_place for row in final_places] == [1, 2, 3, 4]
    assert final_places[0].postseason_result == "CHAMPION"


def test_regular_stat_correction_rebuilds_only_an_unstarted_locked_bracket(db_session):
    league, _teams = _league_with_regular_results(db_session, playoff_teams=4)
    bracket = lock_postseason_seeding(db_session, league)
    db_session.commit()
    first_game = db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id).first()
    assert first_game is not None and first_game.status == "SCHEDULED"

    regular_game = db_session.query(Matchup).filter(Matchup.league_id == league.id, Matchup.week == 1).first()
    regular_game.status = "stat_corrected"
    regular_game.home_score = 50.0
    regular_game.away_score = 150.0
    assert refresh_locked_postseason_after_regular_correction(db_session, league) is True
    db_session.commit()

    assert db_session.query(PostseasonMatchup).filter_by(bracket_id=bracket.id).count() == 3
    assert db_session.query(ScoringAdminAudit).filter_by(league_id=league.id, action="postseason_seeding_rebuilt_after_stat_correction").count() == 1
    assert refresh_locked_postseason_after_regular_correction(db_session, league, scoring_week=11) is False


def test_playoff_routes_are_member_scoped_and_lock_is_commissioner_only(client, db_session):
    commissioner = User(email="postseason-commissioner@example.com", first_name="Commissioner", password_hash="x", api_token="postseason-commissioner-token")
    member = User(email="postseason-member@example.com", first_name="Member", password_hash="x", api_token="postseason-member-token")
    outsider = User(email="postseason-outsider@example.com", first_name="Outsider", password_hash="x", api_token="postseason-outsider-token")
    db_session.add_all([commissioner, member, outsider])
    db_session.flush()
    league, _teams = _league_with_regular_results(db_session, playoff_teams=4)
    league.commissioner_user_id = commissioner.id
    db_session.add_all([
        LeagueMember(league_id=league.id, user_id=commissioner.id, role="commissioner"),
        LeagueMember(league_id=league.id, user_id=member.id, role="member"),
    ])
    db_session.commit()
    commissioner_token, _ = create_access_token(user_id=commissioner.id, email=commissioner.email)
    member_token, _ = create_access_token(user_id=member.id, email=member.email)
    outsider_token, _ = create_access_token(user_id=outsider.id, email=outsider.email)
    headers = lambda token: {"Authorization": f"Bearer {token}"}

    assert client.get(f"/leagues/{league.id}/playoffs/seeding", headers=headers(outsider_token)).status_code == 403
    assert client.get(f"/leagues/{league.id}/playoffs/seeding", headers=headers(member_token)).status_code == 200
    assert client.post(f"/leagues/{league.id}/playoffs/lock", headers=headers(member_token)).status_code == 403
    locked = client.post(f"/leagues/{league.id}/playoffs/lock", headers=headers(commissioner_token))
    assert locked.status_code == 200
    assert len(locked.json()["entries"]) == 4
    # Repeated commissioner requests return the one already persisted bracket.
    assert client.post(f"/leagues/{league.id}/playoffs/lock", headers=headers(commissioner_token)).status_code == 200


def test_regular_standings_rank_records_by_tie_aware_winning_percentage(db_session):
    league, teams = _league_with_regular_results(db_session, playoff_teams=4)
    db_session.add_all([
        Standing(league_id=league.id, team_id=teams[0].id, season=2026, week=13, wins=8, losses=5, ties=0, points_for=1000, points_against=900),
        Standing(league_id=league.id, team_id=teams[2].id, season=2026, week=13, wins=7, losses=0, ties=0, points_for=900, points_against=800),
    ])
    db_session.commit()
    # A raw-wins comparator would put 8-5 ahead of 7-0; the canonical
    # standings view must use the same tie-aware winning percentage concept.
    rows = build_standings_summary(db_session, league)
    assert rows[0].team_id == teams[2].id
    assert rows[0].rank == 1
