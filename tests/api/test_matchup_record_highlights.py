from datetime import datetime, timezone

import pytest
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.standing import Standing
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.services import league_roster_matchup as views, league_weeks
from collegefootballfantasy_api.app.services.scoring_service import recalculate_standings_for_week
from tests.api.scoring_helpers import create_scoring_fixture


@pytest.fixture
def clock(monkeypatch):
    now = [datetime(2026, 9, 2, 12, tzinfo=timezone.utc)]
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return now[0].astimezone(tz) if tz else now[0].replace(tzinfo=None)
    monkeypatch.setattr(views, 'datetime', Frozen)
    monkeypatch.setattr(league_weeks, 'datetime', Frozen)
    return now


def seed(db):
    league, home, away, _, matchup = create_scoring_fixture(db)
    user = User(first_name='Records', email='record-check@example.invalid', password_hash='fixture', api_token='record-check')
    db.add(user); db.flush(); home.owner_user_id=user.id
    matchup.home_score=12; matchup.away_score=6
    db.commit()
    return league,home,away,matchup,user


def read(db, league, matchup, user):
    return views.build_matchup_tab_view(db,league,user,selected_week=matchup.week,matchup_id=matchup.id)


@pytest.mark.parametrize('status',['scheduled','projected','live','delayed','unavailable'])
def test_pending_matchup_records_are_neutral(db_session,clock,status):
    league,home,away,m,user=seed(db_session); m.status=status; db_session.commit()
    result=read(db_session,league,m,user)
    assert result.my_team.record_highlight is None
    assert result.opponent_team.record_highlight is None


def test_final_requires_both_applied_records_and_never_mutates_them(db_session,clock):
    league,home,away,m,user=seed(db_session);m.status='final';db_session.commit()
    assert read(db_session,league,m,user).my_team.record_highlight is None
    recalculate_standings_for_week(db_session,league.id,2026,1);db_session.commit()
    for _ in range(3):
        result=read(db_session,league,m,user)
        assert (result.my_team.record,result.my_team.record_highlight)==('1-0-0','win')
        assert (result.opponent_team.record,result.opponent_team.record_highlight)==('0-1-0','loss')
        assert result.current_matchup_week==1
        assert result.matchup_week_rollover_at==datetime(2026,9,9,4,tzinfo=timezone.utc)
    assert db_session.query(Standing).count()==2
    away_row=db_session.query(Standing).filter_by(team_id=away.id).one()
    away_row.losses=0;db_session.commit()
    result=read(db_session,league,m,user)
    assert result.my_team.record=='1-0-0'
    assert result.my_team.record_highlight is result.opponent_team.record_highlight is None


def test_correction_waits_for_standings_then_colors_corrected_outcome(db_session,clock):
    league,home,away,m,user=seed(db_session);m.status='final'
    recalculate_standings_for_week(db_session,league.id,2026,1);db_session.commit()
    m.away_score=20;m.status='stat_corrected';db_session.commit()
    pending=read(db_session,league,m,user)
    assert pending.my_team.record=='1-0-0'
    assert pending.my_team.record_highlight is pending.opponent_team.record_highlight is None
    recalculate_standings_for_week(db_session,league.id,2026,1);db_session.commit()
    result=read(db_session,league,m,user)
    assert (result.my_team.record,result.my_team.record_highlight)==('0-1-0','loss')
    assert (result.opponent_team.record,result.opponent_team.record_highlight)==('1-0-0','win')
    # A same-winner point correction still requires updated points, not counts alone.
    m.away_score=21;db_session.commit()
    assert read(db_session,league,m,user).my_team.record_highlight is None


def test_ties_and_byes_are_neutral(db_session,clock):
    league,home,away,m,user=seed(db_session);m.status='final';m.away_score=12
    recalculate_standings_for_week(db_session,league.id,2026,1);db_session.commit()
    result=read(db_session,league,m,user)
    assert result.my_team.record=='0-0-1'
    assert result.my_team.record_highlight is result.opponent_team.record_highlight is None
    db_session.delete(m);db_session.commit()
    result=views.build_matchup_tab_view(db_session,league,user,selected_week=1)
    assert result.matchup_id is None
    assert result.my_team.record_highlight is None


def test_highlight_follows_display_rollover_not_operational_reset(db_session,clock):
    league,home,away,m,user=seed(db_session);m.status='final'
    db_session.add(Matchup(league_id=league.id,season=2026,week=2,home_team_id=home.id,away_team_id=away.id,status='scheduled'))
    recalculate_standings_for_week(db_session,league.id,2026,1);db_session.commit()
    for instant in ['2026-09-08T11:59:00+00:00','2026-09-08T12:00:00+00:00','2026-09-09T03:59:59+00:00']:
        clock[0]=datetime.fromisoformat(instant)
        result=views.build_matchup_tab_view(db_session,league,user)
        assert result.week==result.current_matchup_week==1
        assert result.my_team.record_highlight=='win'
    clock[0]=datetime(2026,9,9,4,tzinfo=timezone.utc)
    current=views.build_matchup_tab_view(db_session,league,user)
    history=read(db_session,league,m,user)
    assert current.week==current.current_matchup_week==2
    assert current.my_team.record_highlight is None
    assert history.week==1 and history.current_matchup_week==2
    assert history.my_team.record_highlight is history.opponent_team.record_highlight is None
    m.status='stat_corrected';m.away_score=30
    recalculate_standings_for_week(db_session,league.id,2026,1);db_session.commit()
    assert read(db_session,league,m,user).my_team.record_highlight is None


def test_multiple_digits_and_away_viewer_and_repeated_recalculation(db_session,clock):
    league,home,away,m,user=seed(db_session);m.status='final'
    for week in range(2,13):
        db_session.add(Matchup(league_id=league.id,season=2026,week=week,home_team_id=home.id,away_team_id=away.id,status='final',home_score=12,away_score=6))
    db_session.flush();current=db_session.query(Matchup).filter_by(league_id=league.id,week=12).one()
    clock[0]=datetime(2026,11,18,12,tzinfo=timezone.utc)
    home.owner_user_id=None;away.owner_user_id=user.id
    for _ in range(2): recalculate_standings_for_week(db_session,league.id,2026,12)
    db_session.commit();result=read(db_session,league,current,user)
    assert (result.my_team.record,result.my_team.record_highlight)==('0-12-0','loss')
    assert (result.opponent_team.record,result.opponent_team.record_highlight)==('12-0-0','win')


def test_foreign_season_or_league_standings_cannot_certify_application(db_session,clock):
    league,home,away,m,user=seed(db_session);m.status='final'
    db_session.add(Standing(league_id=league.id,team_id=home.id,season=2025,week=1,wins=1,losses=0,ties=0,points_for=12,points_against=6))
    db_session.commit();result=read(db_session,league,m,user)
    assert result.my_team.record_highlight is None
    other,_,_,_,_=create_scoring_fixture(db_session)
    db_session.add(Standing(league_id=other.id,team_id=home.id,season=2026,week=1,wins=1,losses=0,ties=0,points_for=12,points_against=6))
    db_session.commit();assert read(db_session,league,m,user).my_team.record_highlight is None


def test_actual_http_response_includes_atomic_record_and_result(client,db_session,clock):
    identity=client.post('/auth/signup',json={'first_name':'Record HTTP','email':'record-http@example.com','password':'StrongPass123!'}).json()
    league,home,away,_,m=create_scoring_fixture(db_session)
    home.owner_user_id=identity['user']['id']
    db_session.add(LeagueMember(league_id=league.id,user_id=home.owner_user_id,role='commissioner'))
    m.status='final';m.home_score=12;m.away_score=6
    recalculate_standings_for_week(db_session,league.id,2026,1);db_session.commit()
    response=client.get(f'/leagues/{league.id}/matchup?week=1&matchup_id={m.id}',headers={'Authorization':'Bearer '+identity['access_token']})
    assert response.status_code==200,response.text
    body=response.json()
    assert body['my_team']['record']=='1-0-0' and body['my_team']['record_highlight']=='win'
    assert body['opponent_team']['record']=='0-1-0' and body['opponent_team']['record_highlight']=='loss'
    assert body['current_matchup_week']==body['week']==1
    assert body['matchup_week_rollover_at']=='2026-09-09T04:00:00Z'


def test_matching_aggregate_without_application_receipt_is_not_confirmation(db_session,clock):
    league,home,away,m,user=seed(db_session);m.status='final'
    second=Matchup(league_id=league.id,season=2026,week=2,home_team_id=home.id,away_team_id=away.id,status='final',home_score=6,away_score=12)
    db_session.add(second);db_session.flush()
    recalculate_standings_for_week(db_session,league.id,2026,2);db_session.commit()
    clock[0]=datetime(2026,9,9,12,tzinfo=timezone.utc)
    original=second.record_application_fingerprint
    # Offset two corrections: totals/counts stay identical, but this exact
    # current result has not yet been applied by the standings publisher.
    m.home_score,m.away_score=6,12
    second.home_score,second.away_score=12,6
    db_session.commit()
    result=read(db_session,league,second,user)
    assert result.my_team.record=='1-1-0'
    assert result.my_team.record_highlight is result.opponent_team.record_highlight is None
    assert second.record_application_fingerprint==original
    recalculate_standings_for_week(db_session,league.id,2026,2);db_session.commit()
    result=read(db_session,league,second,user)
    assert result.my_team.record_highlight=='win'
    assert second.record_application_fingerprint!=original
    second.record_application_fingerprint=None;db_session.commit()
    assert read(db_session,league,second,user).my_team.record_highlight is None


def test_application_receipt_and_standings_rollback_together(db_session,clock):
    league,home,away,m,user=seed(db_session);m.status='final';db_session.commit()
    recalculate_standings_for_week(db_session,league.id,2026,1)
    assert m.record_application_fingerprint is not None
    db_session.rollback()
    assert db_session.query(Standing).count()==0
    assert db_session.get(Matchup,m.id).record_application_fingerprint is None


def test_legacy_weekly_writer_publishes_the_same_atomic_receipt(db_session,clock):
    from scripts.compute_weekly_scores import _update_standings
    league,home,away,m,user=seed(db_session);m.status='final';db_session.commit()
    _update_standings(db_session,league.id,2026,1,[m])
    result=read(db_session,league,m,user)
    assert result.my_team.record_highlight=='win'
    first=m.record_application_fingerprint
    _update_standings(db_session,league.id,2026,1,[m])
    assert m.record_application_fingerprint==first
    assert read(db_session,league,m,user).my_team.record=='1-0-0'
