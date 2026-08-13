from datetime import datetime, timedelta, timezone

from conftest import TestingSessionLocal

from collegefootballfantasy_api.app.models.career import LeagueRivalry, UserCareerEvent
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.postseason import PostseasonBracket, PostseasonFinalStanding, PostseasonMatchup, PostseasonRound
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.team_week_score import TeamWeekScore
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services.career_profile import build_career_profile, record_finalized_matchup_events
from collegefootballfantasy_api.app.services.league_rivalries import rivalry_matchup_context, set_rivalry
from scripts.backfill_career_profile import reconcile


def _signup(client, suffix: str) -> tuple[str, User]:
    response = client.post(
        "/auth/signup",
        json={"first_name": suffix.title(), "email": f"{suffix}@example.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    with TestingSessionLocal() as session:
        user = session.query(User).filter(User.email == f"{suffix}@example.com").one()
        user.email_verified_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(user)
        return token, user


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _league_with_two_humans(db, first: User, second: User):
    league = League(name="Career Ledger", commissioner_user_id=first.id, season_year=2026, max_teams=2, status="active")
    db.add(league)
    db.flush()
    first_team = Team(league_id=league.id, name="First Team", owner_user_id=first.id, owner_name=first.first_name, draft_position=1)
    second_team = Team(league_id=league.id, name="Second Team", owner_user_id=second.id, owner_name=second.first_name, draft_position=2)
    db.add_all([first_team, second_team])
    db.flush()
    db.add_all([
        LeagueMember(league_id=league.id, user_id=first.id, role="commissioner"),
        LeagueMember(league_id=league.id, user_id=second.id, role="member"),
    ])
    db.flush()
    return league, first_team, second_team


def test_career_profile_is_derived_from_finalized_ledger_and_public_view_is_safe(client, db_session):
    first_token, first = _signup(client, "career-first")
    _, second = _signup(client, "career-second")
    league, first_team, second_team = _league_with_two_humans(db_session, first, second)
    db_session.add_all([
        Matchup(league_id=league.id, season=2026, week=1, home_team_id=first_team.id, away_team_id=second_team.id, status="final", home_score=125.5, away_score=120.0),
        Matchup(league_id=league.id, season=2026, week=2, home_team_id=first_team.id, away_team_id=second_team.id, status="completed", home_score=100.0, away_score=100.0),
        TeamWeekScore(league_id=league.id, team_id=first_team.id, season=2026, week=1, total_points=125.5),
        TeamWeekScore(league_id=league.id, team_id=first_team.id, season=2026, week=2, total_points=100.0),
    ])
    db_session.commit()

    response = client.get("/users/me/career", headers=_headers(first_token))
    assert response.status_code == 200
    profile = response.json()
    assert profile["record"] == {"wins": 1, "losses": 0, "ties": 1, "win_pct": 0.75}
    assert profile["scoring"]["points_for"] == 225.5
    assert profile["leagues"]["joined"] == 1
    assert profile["matchups"]["completed"] == 2

    public = client.get(f"/users/{first.id}/career", headers=_headers(first_token))
    assert public.status_code == 200
    assert "waivers" not in public.json()
    assert "scoring" not in public.json()


def test_career_profile_counts_regular_season_first_place_from_final_standings(client, db_session):
    token, first = _signup(client, "career-first-place")
    _, second = _signup(client, "career-first-place-opponent")
    league, first_team, _ = _league_with_two_humans(db_session, first, second)
    db_session.add(PostseasonFinalStanding(
        league_id=league.id,
        season=2026,
        team_id=first_team.id,
        final_place=2,
        regular_season_rank=1,
        postseason_result="RUNNER_UP",
        finalized_at=datetime.now(timezone.utc),
    ))
    db_session.commit()

    profile = client.get("/users/me/career", headers=_headers(token)).json()
    assert profile["postseason"] == {
        "appearances": 1,
        "championships": 0,
        "regular_season_first_place": 1,
    }


def test_rival_selection_is_human_only_and_emits_one_auditable_event(client, db_session):
    first_token, first = _signup(client, "rival-first")
    _, second = _signup(client, "rival-second")
    league, first_team, second_team = _league_with_two_humans(db_session, first, second)
    db_session.commit()

    selected = client.put(f"/leagues/{league.id}/rival", json={"rival_team_id": second_team.id}, headers=_headers(first_token))
    assert selected.status_code == 200
    assert selected.json()["rival_team_id"] == second_team.id
    assert db_session.query(LeagueRivalry).count() == 1
    assert db_session.query(UserCareerEvent).filter(UserCareerEvent.event_type == "RIVAL_SELECTED").count() == 1


def test_rival_change_is_blocked_for_seven_days_after_a_completed_rivalry_matchup(client, db_session):
    first_token, first = _signup(client, "rival-cooldown-first")
    _, second = _signup(client, "rival-cooldown-second")
    _, third = _signup(client, "rival-cooldown-third")
    league, first_team, second_team = _league_with_two_humans(db_session, first, second)
    third_team = Team(league_id=league.id, name="Third Team", owner_user_id=third.id, owner_name=third.first_name)
    db_session.add_all([third_team, LeagueMember(league_id=league.id, user_id=third.id, role="member")])
    db_session.commit()

    assert client.put(
        f"/leagues/{league.id}/rival", json={"rival_team_id": second_team.id}, headers=_headers(first_token)
    ).status_code == 200
    db_session.add(Matchup(
        league_id=league.id, season=2026, week=1, home_team_id=first_team.id, away_team_id=second_team.id,
        status="final", home_score=100.0, away_score=90.0,
    ))
    db_session.commit()

    blocked = client.put(
        f"/leagues/{league.id}/rival", json={"rival_team_id": third_team.id}, headers=_headers(first_token)
    )
    assert blocked.status_code == 409
    rivalry = db_session.query(LeagueRivalry).filter(LeagueRivalry.team_id == first_team.id).one()
    rivalry.changed_at = datetime.now(timezone.utc) - timedelta(days=7, seconds=1)
    db_session.commit()
    allowed = client.put(
        f"/leagues/{league.id}/rival", json={"rival_team_id": third_team.id}, headers=_headers(first_token)
    )
    assert allowed.status_code == 200
    assert allowed.json()["rival_team_id"] == third_team.id

    selected_again = client.put(f"/leagues/{league.id}/rival", json={"rival_team_id": second_team.id}, headers=_headers(first_token))
    assert selected_again.status_code == 200
    assert db_session.query(UserCareerEvent).filter(UserCareerEvent.event_type == "RIVAL_SELECTED").count() == 1


def test_career_backfill_dry_run_does_not_flush_or_create_rows(client, db_session):
    _, first = _signup(client, "backfill-first")
    _, second = _signup(client, "backfill-second")
    league, first_team, second_team = _league_with_two_humans(db_session, first, second)
    db_session.add(Matchup(
        league_id=league.id, season=2026, week=1, home_team_id=first_team.id, away_team_id=second_team.id,
        status="final", home_score=101.0, away_score=99.0,
    ))
    db_session.commit()
    before = db_session.query(UserCareerEvent).count()
    summary = reconcile(db_session, apply=False)
    assert summary["mode"] == "dry-run"
    assert summary["would_create"] > 0
    assert summary["database_writes"] == 0
    assert db_session.query(UserCareerEvent).count() == before


def test_finalized_rivalry_matchup_writes_one_immutable_rival_event(client, db_session):
    first_token, first = _signup(client, "rival-final-first")
    _, second = _signup(client, "rival-final-second")
    league, first_team, second_team = _league_with_two_humans(db_session, first, second)
    db_session.commit()
    assert client.put(
        f"/leagues/{league.id}/rival",
        json={"rival_team_id": second_team.id},
        headers=_headers(first_token),
    ).status_code == 200
    matchup = Matchup(
        league_id=league.id,
        season=2026,
        week=1,
        home_team_id=first_team.id,
        away_team_id=second_team.id,
        status="FINAL",
        home_score=110.0,
        away_score=100.0,
    )
    db_session.add(matchup)
    db_session.flush()

    # Rivalries are unilateral: both managers get their final-matchup event,
    # while only the manager who selected this rival receives the Rival Week event.
    assert record_finalized_matchup_events(db_session, [matchup]) == 3
    db_session.commit()
    assert record_finalized_matchup_events(db_session, [matchup]) == 0
    assert db_session.query(UserCareerEvent).filter(
        UserCareerEvent.user_id == first.id,
        UserCareerEvent.event_type == "RIVAL_MATCHUP_WON",
    ).count() == 1


def test_backfill_apply_is_idempotent_after_a_reviewed_dry_run(client, db_session):
    _, first = _signup(client, "backfill-apply-first")
    _, second = _signup(client, "backfill-apply-second")
    league, first_team, second_team = _league_with_two_humans(db_session, first, second)
    db_session.add(Matchup(
        league_id=league.id, season=2026, week=1, home_team_id=first_team.id, away_team_id=second_team.id,
        status="FINAL", home_score=91.0, away_score=90.0,
    ))
    db_session.commit()

    dry_run = reconcile(db_session, apply=False)
    applied = reconcile(db_session, apply=True)
    rerun = reconcile(db_session, apply=False)
    assert dry_run["would_create"] == applied["created"]
    assert applied["created"] > 0
    assert rerun["would_create"] == 0
    assert rerun["already_recorded"] == rerun["planned"]


def test_championship_context_uses_the_postseason_ledger_not_rivalry_state(client, db_session):
    _, first = _signup(client, "championship-first")
    _, second = _signup(client, "championship-second")
    league, first_team, second_team = _league_with_two_humans(db_session, first, second)
    matchup = Matchup(
        league_id=league.id, season=2026, week=13, home_team_id=first_team.id, away_team_id=second_team.id,
        status="scheduled", home_score=0.0, away_score=0.0,
    )
    db_session.add(matchup)
    db_session.flush()
    bracket = PostseasonBracket(
        league_id=league.id, season=2026, bracket_type="CHAMPIONSHIP", total_teams=2, total_rounds=1,
    )
    db_session.add(bracket)
    db_session.flush()
    round_ = PostseasonRound(bracket_id=bracket.id, round_number=1, week=13, round_type="CHAMPIONSHIP")
    db_session.add(round_)
    db_session.flush()
    db_session.add(PostseasonMatchup(
        bracket_id=bracket.id, round_id=round_.id, fantasy_matchup_id=matchup.id, slot_number=1,
        advancement_rule="WINNER", team_a_id=first_team.id, team_b_id=second_team.id,
    ))
    db_session.commit()

    context = rivalry_matchup_context(db_session, league, first, matchup)
    assert context.is_championship is True
    assert context.is_rivalry_matchup is False
