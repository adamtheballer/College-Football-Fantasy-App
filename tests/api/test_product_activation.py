from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.product_event import ProductEvent
from collegefootballfantasy_api.app.models.challenge_experience import ChallengeAnalyticsPreference
from collegefootballfantasy_api.app.models.weekly_challenge import ChallengeRound, WeeklyChallenge, ChallengeEntry, ChallengeAward
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.matchup import Matchup
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.models.injury import Injury
from collegefootballfantasy_api.app.models.trade_offer import TradeOffer
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.services import app_review, product, player_rankings
from collegefootballfantasy_api.app.services.player_data_health import run_due_product_health
from collegefootballfantasy_api.app.schemas.app_review import AppReviewClaim
from collegefootballfantasy_api.app.core.config import settings
from test_performance_rankings import player, game, score


def account(client, suffix='one'):
    r=client.post('/auth/signup',json={'first_name':'Product QA','email':f'product-{suffix}@example.com','password':'StrongPass123!'}).json()
    uid=r['user']['id']
    return uid, {'Authorization':f"Bearer {r['access_token']}", 'X-CFFB-Challenge-Account':str(uid),
        'Origin':'capacitor://localhost','X-CFFB-Native-Session':'ios','X-CFFB-Review-Account':str(uid),'X-CFFB-Release-Account':str(uid)}


def challenge(db, **kw):
    now=datetime.now(timezone.utc)
    r=ChallengeRound(season=2026,week=8,next_rollover_at=now+timedelta(days=7));db.add(r);db.flush()
    c=WeeklyChallenge(round_id=r.id,kind='lock',status='open',published_at=now,lock_at=now+timedelta(days=1),config={},**kw)
    db.add(c);db.flush();return c


def test_optional_events_idempotent_validation_account_bound_and_authoritative_submissions(client,db_session):
    uid,h=account(client);c=challenge(db_session);db_session.commit()
    body={'kind':'challenge_view','challenge_id':c.id}
    assert client.post('/product/events',headers=h,json=body).json()=={'recorded':True}
    assert client.post('/product/events',headers=h,json=body).json()=={'recorded':False}
    assert client.post('/product/events',headers={**h,'X-CFFB-Challenge-Account':'999'},json=body).status_code==409
    assert client.post('/product/events',headers=h,json={**body,'email':'not-allowed'}).status_code==422
    assert client.post('/product/events',headers=h,json={'kind':'made-up'}).status_code==422
    assert client.post('/product/events',headers=h,json={'kind':'session','app_build':'unsafe build!'}).status_code==422
    assert client.post('/product/events',headers=h,json={'kind':'challenge_submit','challenge_id':c.id}).status_code==409
    assert client.post('/product/events',headers=h,json={'kind':'challenge_view','challenge_id':999}).status_code==404
    assert client.get('/product/admin/participation',headers=h).status_code==403
    assert client.get('/product/home-actions').status_code==401
    assert db_session.query(ProductEvent).count()==1


def test_opt_out_and_dnt_prevent_storage_and_metrics_exclude_confirmed_tests(client,db_session):
    uid,h=account(client);admin,ah=account(client,'admin');test,th=account(client,'test')
    db_session.get(User,admin).is_admin=True;db_session.get(User,test).is_test_account=True;db_session.commit()
    assert client.post('/product/events',headers={**h,'DNT':'1'},json={'kind':'session'}).json()=={'recorded':False}
    pref=ChallengeAnalyticsPreference(user_id=uid,enabled=False);db_session.add(pref);db_session.commit()
    assert client.post('/product/events',headers=h,json={'kind':'session'}).json()=={'recorded':False}
    pref.enabled=True;db_session.commit()
    for headers in [h,ah,th]:assert client.post('/product/events',headers=headers,json={'kind':'session','platform':'ios','app_version':'1.0.4','app_build':'48'}).status_code==200
    c=challenge(db_session)
    for user_id in [uid,admin,test]:db_session.add(ChallengeEntry(user_id=user_id,challenge_id=c.id,status='submitted',submitted_at=datetime.now(timezone.utc),selections=[]))
    db_session.commit()
    m=client.get('/product/admin/participation',headers=ah).json()
    assert m['active_accounts']==m['challenge_submitters']==m['submitted_entries']==1
    assert m['native_versions']=={'ios 1.0.4 (48)':1}
    assert m['review_authorizations']==m['review_invocations']==0
    assert client.get('/product/admin/participation?days=91',headers=ah).status_code==422


def test_review_waits_for_meaningful_use_and_invocation_ack_is_separate_once(client,db_session,monkeypatch):
    monkeypatch.setattr(settings,'ios_app_review_enabled',True)
    uid,h=account(client)
    assert client.get('/app-review/state',headers=h).json()['eligible'] is False
    assert client.post('/app-review/claim',headers=h,json={'app_version':'1.0.4','app_build':'48'}).json()['authorization']=='not_eligible'
    assert db_session.get(User,uid).review_request_claimed_at is None
    c=challenge(db_session);db_session.add(ChallengeEntry(challenge_id=c.id,user_id=uid,status='draft',selections=[]));db_session.commit()
    assert not app_review.meaningful_use(db_session,uid)
    db_session.query(ChallengeEntry).filter_by(user_id=uid).update({'status':'submitted'});db_session.commit()
    grant=client.post('/app-review/claim',headers=h,json={'app_version':'1.0.4','app_build':'48'}).json()
    assert grant['authorization']=='granted' and grant['review_request_invoked_at'] is None
    stamp=client.post('/app-review/invoked',headers=h).json()['review_request_invoked_at']
    assert stamp and client.post('/app-review/invoked',headers=h).json()['review_request_invoked_at']==stamp
    assert client.post('/app-review/claim',headers=h,json={'app_version':'1.0.5','app_build':'49'}).json()['authorization']=='already_claimed'


def test_finalized_matchup_qualifies_and_new_users_skip_historical_update(client,db_session):
    uid,h=account(client);other,_=account(client,'other')
    l=League(name='Played',season_year=2026);db_session.add(l);db_session.flush()
    a=Team(league_id=l.id,owner_user_id=uid,name='A');b=Team(league_id=l.id,owner_user_id=other,name='B');db_session.add_all([a,b]);db_session.flush()
    m=Matchup(league_id=l.id,season=2026,week=1,home_team_id=a.id,away_team_id=b.id,status='scheduled');db_session.add(m);db_session.commit()
    assert not app_review.meaningful_use(db_session,uid)
    m.status='final';db_session.commit();assert app_review.meaningful_use(db_session,uid)
    assert client.post('/release-notes/1.03/claim',headers=h,json={}).json()['authorization']=='already_seen'


def test_home_actions_only_own_starters_incoming_trades_and_canonical_lock(client,db_session,monkeypatch):
    uid,h=account(client);other,_=account(client,'other');now=datetime.now(timezone.utc)
    from collegefootballfantasy_api.app.services import home_actions
    monkeypatch.setattr(home_actions,'calendar_cfb_week',lambda season,now:8)
    l=League(name='Action league',season_year=2026);db_session.add(l);db_session.flush()
    db_session.add(LeagueMember(user_id=uid,league_id=l.id,role='member'))
    a=Team(league_id=l.id,owner_user_id=uid,name='Mine');b=Team(league_id=l.id,owner_user_id=other,name='Other');db_session.add_all([a,b]);db_session.flush()
    p=player(db_session,'Injured starter');bench=player(db_session,'Benched')
    db_session.add_all([RosterEntry(league_id=l.id,team_id=a.id,player_id=p.id,slot='RB',status='starter'),RosterEntry(league_id=l.id,team_id=a.id,player_id=bench.id,slot='BENCH',status='bench')])
    db_session.add_all([Injury(player_id=x.id,season=2026,week=8,status='OUT') for x in [p,bench]])
    db_session.add(TeamSchedule(team_name='Texas',season=2026,week=8,location='home',kickoff_at=now+timedelta(hours=2)))
    trade=TradeOffer(league_id=l.id,proposing_team_id=b.id,receiving_team_id=a.id,status='proposed');db_session.add(trade);db_session.commit()
    actions=client.get('/product/home-actions',headers=h).json()['data']
    assert len(actions)==3 and 'Injured starter' in actions[0]['title']
    assert all('Benched' not in r['title'] for r in actions)
    assert any(r['href']==f'/leagues/{l.id}/trades/{trade.id}' for r in actions)
    db_session.query(LeagueMember).filter_by(user_id=uid,league_id=l.id).delete();db_session.commit()
    assert client.get('/product/home-actions',headers=h).json()['data']==[]
    assert not any(r['key'].startswith('injury:') for r in client.get('/product/home-actions',headers=account(client,'outsider')[1]).json()['data'])


def test_health_observes_evidenced_gap_without_inventing_bench_scores_and_hourly_retention(client,db_session,monkeypatch):
    from collegefootballfantasy_api.app.models.player_stat import PlayerStat
    monkeypatch.setattr(player_rankings,'calendar_cfb_week',lambda season:3)
    p=player(db_session,'Missing final fact');bench=player(db_session,'Unknown participation');game(db_session)
    db_session.add(PlayerStat(player_id=p.id,season=2026,week=2,verified=True,stats={'rush_yards':20}))
    uid,h=account(client);db_session.get(User,uid).is_admin=True
    now=datetime.now(timezone.utc)
    db_session.add(ProductEvent(user_id=uid,kind='session',dedupe_key='old',at=now-timedelta(days=91),platform='web'));db_session.commit()
    report=client.get('/product/admin/player-health',headers=h).json()
    assert report['status']=='attention' and report['feed_gap_count']==1 and report['awaiting_stats_or_participation']==2
    assert report['sample_player_ids']==[p.id] and bench.id not in report['sample_player_ids']
    assert run_due_product_health(db_session,2026,now)['status']=='attention'
    assert run_due_product_health(db_session,2026,now+timedelta(minutes=1))=={'status':'not_due'}
    assert db_session.query(ProductEvent).count()==0


def test_league_group_filters_before_top_ten_and_rank_and_checks_membership(client,db_session):
    uid,h=account(client);other,oh=account(client,'other');c=challenge(db_session);c.status='final'
    l=League(name='Friends');db_session.add(l);db_session.flush();db_session.add(LeagueMember(user_id=uid,league_id=l.id,role='member'))
    for user_id,points in [(uid,2),(other,10)]:
        e=ChallengeEntry(user_id=user_id,challenge_id=c.id,status='submitted',selections=[]);db_session.add(e);db_session.flush()
        db_session.add(ChallengeAward(entry_id=e.id,round_id=c.round_id,user_id=user_id,points=points,source_hash='test'))
    db_session.commit()
    result=client.get('/weekly-challenges/leaderboard',params={'season':2026,'league_id':l.id},headers=h).json()
    assert [(r['user_id'],r['rank'],r['points']) for r in result['data']]==[(uid,1,2)]
    assert client.get('/weekly-challenges/leaderboard',params={'season':2026,'league_id':l.id},headers=oh).status_code==403


def test_failed_health_scan_persists_failed_receipt_and_keeps_hourly_backoff(client,db_session,monkeypatch):
    import pytest
    from collegefootballfantasy_api.app.services import player_data_health
    from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState
    monkeypatch.setattr(player_data_health,'player_health',lambda db,season: (_ for _ in ()).throw(RuntimeError('synthetic source outage')))
    now=datetime.now(timezone.utc)
    with pytest.raises(RuntimeError,match='synthetic source outage'):
        run_due_product_health(db_session,2026,now)
    state=db_session.query(ProviderSyncState).filter_by(provider='cffb',feed='product_health').one()
    assert state.status=='failed' and state.consecutive_failures==1
    assert run_due_product_health(db_session,2026,now+timedelta(minutes=1))=={'status':'not_due'}


def test_duplicate_events_from_concurrent_devices_are_one_daily_receipt(client):
    import pytest
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from conftest import TestingSessionLocal, engine
    from collegefootballfantasy_api.app.schemas.product import ProductEventCreate
    if engine.dialect.name!='postgresql':pytest.skip('PostgreSQL account-row concurrency check')
    uid,_=account(client)
    barrier=Barrier(2)
    def device():
        with TestingSessionLocal() as db:
            user=db.get(User,uid);barrier.wait(timeout=5)
            return product.record_event(db,user,ProductEventCreate(kind='session'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(lambda _:device(),range(2)))
    assert sorted(result)==[False,True]
    with TestingSessionLocal() as db:assert db.query(ProductEvent).count()==1


def test_injury_health_uses_every_official_source_check_not_last_changed_injury(client,db_session,monkeypatch):
    from collegefootballfantasy_api.app.models.provider_sync_state import ProviderSyncState
    from collegefootballfantasy_api.app.services.provider_cache import scope_dict_to_key
    from collegefootballfantasy_api.app.services import player_data_health
    monkeypatch.setattr(player_data_health,'calendar_cfb_week',lambda season:8)
    fixed=datetime(2026,10,20,18,tzinfo=timezone.utc)
    monkeypatch.setattr(player_data_health,'utcnow',lambda:fixed)
    uid,h=account(client);db_session.get(User,uid).is_admin=True
    now=datetime.now(timezone.utc)
    now=fixed
    for conference in ['SEC','ACC','BIG12','BIG10']:
        db_session.add(ProviderSyncState(provider='official_conference_reports',feed='injuries_week',
            scope_key=scope_dict_to_key({'season':2026,'week':8,'conference':conference}),status='ready',last_success_at=now))
    db_session.commit()
    report=client.get('/product/admin/player-health',headers=h).json()
    assert report['injury_feed_status']=='current' and set(report['injury_sources'].values())=={'current'}
    state=db_session.query(ProviderSyncState).filter(ProviderSyncState.scope_key.like('%BIG12%')).one();state.status='failed';db_session.commit()
    report=client.get('/product/admin/player-health',headers=h).json()
    assert report['injury_sources']['BIG12']=='failed' and report['injury_feed_status']=='stale' and report['status']=='attention'
