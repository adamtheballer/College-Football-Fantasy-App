from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_challenge import (
    WeeklyChallenge, ChallengeRound, ChallengeEntry, ChallengeAward, ChallengeScore,
    ChallengeDuel, ChallengeDuelSeat, ChallengeRecognition, ChallengeAudit,
)
from collegefootballfantasy_api.app.schemas.weekly_challenge import EntryWrite
from collegefootballfantasy_api.app.services import weekly_challenges as svc
from collegefootballfantasy_api.app.services.league_weeks import calendar_matchup_display_week, matchup_display_rollover_at
from conftest import TestingSessionLocal, engine

BASE = '/weekly-challenges'
ADMIN = '/admin/weekly-challenges'
NOW = datetime(2026, 9, 2, 16, tzinfo=timezone.utc)
KICKOFF = datetime(2026, 9, 5, 16, tzinfo=timezone.utc)


@pytest.fixture
def world(client, db_session, monkeypatch):
    clock = [NOW]
    monkeypatch.setattr(svc, 'utcnow', lambda: clock[0])
    monkeypatch.setattr(svc.settings, 'current_season_year', 2026)
    def account(index):
        r = client.post('/auth/signup', json={'first_name': f'Manager {index}', 'email': f'challenge{index}@example.com', 'password': 'StrongPass123!'})
        assert r.status_code == 201, r.text
        value = r.json()
        return value['user']['id'], {'Authorization': f"Bearer {value['access_token']}"}
    accounts = [account(i) for i in range(4)]
    admin = db_session.get(User, accounts[0][0]); admin.is_admin = True
    games = []
    for i in range(12):
        game = Game(external_id=f'challenge-game-{i}', season=2026, week=1, season_type='regular', schedule_status='scheduled', start_date=KICKOFF+timedelta(minutes=30*i), home_team='Alabama' if i == 0 else f'Home {i}', away_team=f'Away {i}')
        db_session.add(game); games.append(game)
    db_session.flush()
    players = []
    for i, position in enumerate(['QB', 'RB', 'WR', 'TE', 'RB', 'QB', 'WR']):
        p = Player(name=f'Challenge Athlete {i}', school='Alabama', position=position, sheet_source_sheet_id=f'canonical-correction:2026:challenge-fixture-{i}', sheet_projected_season_points=100)
        db_session.add(p); players.append(p)
    db_session.commit()
    r = client.post(f'{ADMIN}/rounds/2026/1', headers=accounts[0][1])
    assert r.status_code == 200, r.text
    round_ = r.json()
    challenges = {c['kind']: c for c in round_['challenges']}
    return {'accounts': accounts, 'games': games, 'players': players, 'clock': clock, 'round': round_, 'challenges': challenges, 'db': db_session, 'client': client}


def publish(w, kind, **changes):
    c = w['challenges'][kind]; games = w['games']
    ids = [g.id for g in games[:12 if kind == 'slate12' else 5 if kind == 'duels' else 3 if kind == 'upset' else 1]]
    config = {'expected_version': c['version'], 'game_ids': ids, 'player_ids': [], 'featured_game_id': ids[0] if kind == 'slate12' else None, 'underdogs': []}
    if kind == 'upset': config['underdogs'] = [{'game_id': g.id, 'team': g.away_team, 'points': i+1} for i,g in enumerate(games[:3])]
    if kind == 'fantasy5': config['player_ids'] = [p.id for p in w['players']]
    config.update(changes)
    client = w['client']; headers = w['accounts'][0][1]
    r = client.put(f'{ADMIN}/challenges/{c["id"]}', headers=headers, json=config)
    assert r.status_code == 200, r.text
    c = r.json()
    r = client.post(f'{ADMIN}/challenges/{c["id"]}/publish', headers=headers, json={'expected_version':c['version'], 'reason':'Approved test fixture'})
    assert r.status_code == 200, r.text
    w['challenges'][kind] = r.json()
    return r.json()


def picks(w, kind):
    if kind == 'fantasy5': return [{'player_id':p.id, 'slot':slot} for p,slot in zip(w['players'][:5], ['QB','RB','WR','TE','FLEX'])]
    n = {'slate12':12, 'upset':3, 'duels':5, 'lock':1}[kind]
    return [{'game_id':g.id, 'team':g.away_team if kind == 'upset' else g.home_team} for g in w['games'][:n]]


def submit(w, kind, user=1, **changes):
    payload = {'expected_revision':0, 'submit':True, 'selections':picks(w,kind), 'tiebreaker':45 if kind=='slate12' else None}
    payload.update(changes)
    return w['client'].put(f'{BASE}/challenges/{w["challenges"][kind]["id"]}/entry', headers=w['accounts'][user][1], json=payload)


def finalize(w, kind, *, status='final', home=30, away=20):
    for g in w['games']:
        g.schedule_status=status; g.home_points=home; g.away_points=away
    w['db'].commit()
    w['clock'][0]=KICKOFF+timedelta(days=1)
    c=svc.challenge_or_404(w['db'],w['challenges'][kind]['id'],lock=True)
    return svc.settle(w['db'],c)


@pytest.mark.parametrize('kind', list(svc.KINDS))
def test_all_five_formats_submit_and_edit_one_official_entry(world, kind):
    w=world; c=publish(w,kind)
    r=submit(w,kind); assert r.status_code==200,r.text
    first=r.json(); assert first['status']=='submitted' and first['revision']==1
    r=submit(w,kind,expected_revision=1); assert r.status_code==200
    assert r.json()['id']==first['id'] and r.json()['revision']==2
    assert w['db'].query(ChallengeEntry).filter_by(challenge_id=c['id']).count()==1
    stale=submit(w,kind); assert stale.status_code==409
    assert stale.json()['detail']['code']=='VERSION_CONFLICT'


@pytest.mark.parametrize('offset', [-1,0,1])
def test_exact_five_minute_cutoff_and_stale_direct_api(world,offset):
    w=world;c=publish(w,'lock');w['clock'][0]=KICKOFF-timedelta(minutes=5)+timedelta(microseconds=offset)
    r=submit(w,'lock')
    assert r.status_code==(200 if offset<0 else 409)
    if offset>=0:
        assert r.json()['detail']['code']=='DEADLINE_PASSED'
        assert w['db'].query(ChallengeEntry).count()==0
        assert w['client'].get(f'{BASE}/challenges/{c["id"]}',headers=w['accounts'][1][1]).json()['state'].startswith('Closed')


def test_already_started_game_and_schedule_repair_cannot_reopen(world):
    w=world;c=publish(w,'lock')
    w['games'][0].schedule_status='in_progress';w['db'].commit()
    assert submit(w,'lock').status_code==409
    w['games'][0].schedule_status='scheduled';w['db'].commit()
    assert submit(w,'lock').status_code==409
    assert w['db'].query(ChallengeEntry).count()==0


def test_published_slate_cannot_be_replaced_and_wrong_week_rejected(world):
    w=world;c=publish(w,'lock')
    r=w['client'].put(f'{ADMIN}/challenges/{c["id"]}',headers=w['accounts'][0][1],json={'expected_version':c['version'],'game_ids':[w['games'][1].id]})
    assert r.status_code==409 and r.json()['detail']['code']=='IMMUTABLE_RULES'
    w['games'][0].week=2;w['db'].commit()
    assert submit(w,'lock').status_code==503


def test_unpublished_configuration_private_and_not_enterable(world):
    w=world;c=w['challenges']['upset']
    r=w['client'].put(f'{ADMIN}/challenges/{c["id"]}',headers=w['accounts'][0][1],json={'expected_version':0,'game_ids':[g.id for g in w['games'][:3]],'underdogs':[{'game_id':w['games'][0].id,'team':w['games'][0].home_team,'points':5}]})
    assert r.status_code==200
    public=w['client'].get(f'{BASE}/challenges/{c["id"]}',headers=w['accounts'][1][1]).json()
    assert public['games']==public['players']==public['underdogs']==[] and public['draft_config'] is None
    assert submit(w,'upset').json()['detail']['code']=='NOT_PUBLISHED'
    r=w['client'].post(f'{ADMIN}/challenges/{c["id"]}/validate',headers=w['accounts'][0][1])
    assert not r.json()['valid']


def test_unconfigured_admin_draft_has_complete_empty_contract(world):
    for c in world['round']['challenges']:
        assert c['draft_config']=={'game_ids':[], 'player_ids':[], 'featured_game_id':None, 'underdogs':[]}


@pytest.mark.parametrize('kind,changes',[
 ('slate12',{'selections':[]}),('slate12',{'tiebreaker':None}),('slate12',{'tiebreaker':-1}),
 ('upset',{'selections':[]}),('lock',{'selections':[{'game_id':9999,'team':'Foreign'}]}),
 ('fantasy5',{'selections':[]}),('duels',{'selections':[]})])
def test_incomplete_and_foreign_entries_rejected(world,kind,changes):
    publish(world,kind);assert submit(world,kind,**changes).status_code==422
    assert world['db'].query(ChallengeEntry).count()==0


def test_draft_saved_then_submitted_and_invalid_player_slots(world):
    w=world;publish(w,'fantasy5')
    r=submit(w,'fantasy5',submit=False,selections=picks(w,'fantasy5')[:2]);assert r.status_code==200 and r.json()['status']=='draft'
    r=submit(w,'fantasy5',expected_revision=1);assert r.status_code==200
    wrong=picks(w,'fantasy5');wrong[0]['player_id']=w['players'][1].id
    assert submit(w,'fantasy5',user=2,selections=wrong).status_code==422
    dup=picks(w,'fantasy5');dup[-1]['player_id']=dup[1]['player_id']
    assert submit(w,'fantasy5',user=2,selections=dup).status_code==422


def test_unauthorized_admin_and_cross_user_entry_boundaries(world):
    w=world;c=publish(w,'lock');assert submit(w,'lock').status_code==200
    assert w['client'].get(f'{BASE}/challenges/{c["id"]}/entry',headers=w['accounts'][2][1]).json() is None
    assert w['client'].get(f'{BASE}/current').status_code==401
    assert w['client'].post(f'{ADMIN}/rounds/2026/2',headers=w['accounts'][1][1]).status_code==403
    assert w['client'].get(f'{ADMIN}/challenges/{c["id"]}/audit',headers=w['accounts'][1][1]).status_code==403
    assert submit(w,'lock',user_id=w['accounts'][2][0]).status_code==422


def test_lock_scoring_idempotency_correction_and_public_profile_privacy(world):
    w=world;publish(w,'lock');assert submit(w,'lock').status_code==200
    assert finalize(w,'lock')=='final'
    award=w['db'].query(ChallengeAward).one();assert award.points==5
    c=svc.challenge_or_404(w['db'],w['challenges']['lock']['id'],lock=True)
    svc.settle(w['db'],c);assert w['db'].query(ChallengeAward).count()==1 and award.revision==1
    w['games'][0].home_points=10;w['db'].commit();svc.settle(w['db'],c)
    w['db'].refresh(award);assert award.points==0 and award.revision==2
    assert not w['db'].query(ChallengeRecognition).filter_by(active=True).all()
    p=w['client'].get(f'{BASE}/participants/{w["accounts"][1][0]}',headers=w['accounts'][2][1]).json()
    assert set(p)=={'user_id','display_name','username','avatar_url','profile_url','recognition'}
    assert w['db'].query(ChallengeAudit).filter_by(action='correction').count()>=1


def test_slate12_tiebreaker_ties_and_void_featured_game(world):
    w=world;publish(w,'slate12')
    for i,total in [(1,48),(2,52),(3,70)]:assert submit(w,'slate12',user=i,tiebreaker=total).status_code==200
    finalize(w,'slate12')
    scores=w['db'].query(ChallengeScore).order_by(ChallengeScore.entry_id).all()
    assert [s.rank for s in scores]==[1,1,3]
    assert [a.points for a in w['db'].query(ChallengeAward)]==[12,12,12]
    w['games'][0].schedule_status='canceled';w['db'].commit()
    svc.settle(w['db'],svc.challenge_or_404(w['db'],w['challenges']['slate12']['id'],lock=True))
    w['db'].expire_all();scores=w['db'].query(ChallengeScore).all()
    assert all(s.rank==1 and s.tiebreaker_error is None for s in scores)
    assert all(a.points==11 for a in w['db'].query(ChallengeAward))


def test_upset_points_are_published_fixed_weights(world):
    w=world;publish(w,'upset');assert submit(w,'upset').status_code==200
    finalize(w,'upset',home=10,away=20)
    assert w['db'].query(ChallengeAward).one().points==6


def test_fantasy_missing_stats_processing_then_canonical_totals_and_corrections(world):
    w=world;publish(w,'fantasy5')
    for user in (1,2,3):assert submit(w,'fantasy5',user=user).status_code==200
    assert finalize(w,'fantasy5')=='processing' and w['db'].query(ChallengeAward).count()==0
    for p in w['players']:
        w['db'].add(PlayerGameStat(player_id=p.id,game_id=w['games'][0].id,season=2026,week=1,source='espn_final_boxscore',stats={'rush_yards':10,'receptions':0}))
    w['db'].commit()
    c=svc.challenge_or_404(w['db'],w['challenges']['fantasy5']['id'],lock=True);assert svc.settle(w['db'],c)=='final'
    assert [a.points for a in w['db'].query(ChallengeAward)]==[10,10,10]
    assert all(s.raw_points==5 for s in w['db'].query(ChallengeScore))
    # Frozen config, rather than later environment scoring changes, drives corrections.
    before=w['db'].query(ChallengeAward).count()
    fact=w['db'].query(PlayerGameStat).first();fact.stats={'rush_yards':20};w['db'].commit();svc.settle(w['db'],c)
    assert w['db'].query(ChallengeAward).count()==before and all(a.points==10 for a in w['db'].query(ChallengeAward))
    fact.stats={'_scoring_incomplete':True};w['db'].commit();assert svc.settle(w['db'],c)=='processing'
    assert all(a.points==0 for a in w['db'].query(ChallengeAward))


@pytest.mark.parametrize('status', ['canceled','postponed','delayed'])
def test_disrupted_games_and_no_contest_awards(world,status):
    w=world;publish(w,'lock');assert submit(w,'lock').status_code==200
    if status in {'postponed','delayed'}: w['games'][0].start_date=matchup_display_rollover_at(2026,1)+timedelta(days=1)
    result=finalize(w,'lock',status=status)
    assert result=='no_contest' and w['db'].query(ChallengeAward).one().points==0
    assert w['db'].query(ChallengeRecognition).filter_by(active=True).count()==0


def test_delayed_game_inside_round_stays_processing_without_fake_zero(world):
    w=world;publish(w,'lock');assert submit(w,'lock').status_code==200
    assert finalize(w,'lock',status='delayed')=='processing'
    assert w['db'].query(ChallengeAward).count()==0
    assert w['db'].query(ChallengeScore).one().raw_points is None


def test_duel_acceptance_limits_roles_privacy_and_ties(world):
    w=world;c=publish(w,'duels')
    for i in (1,2,3):assert submit(w,'duels',user=i).status_code==200
    headers=w['accounts'][1][1];uid=w['accounts'][2][0]
    r=w['client'].post(f'{BASE}/challenges/{c["id"]}/duels',headers=headers,json={'invitee_id':uid});assert r.status_code==201,r.text
    did=r.json()[0]['id']
    assert w['client'].post(f'{BASE}/challenges/{c["id"]}/duels',headers=headers,json={'invitee_id':uid}).status_code==409
    assert w['client'].post(f'{BASE}/challenges/{c["id"]}/duels',headers=headers,json={'invitee_id':w['accounts'][1][0]}).status_code==422
    assert w['client'].post(f'{BASE}/challenges/{c["id"]}/duels/{did}/accept',headers=w['accounts'][3][1],json={}).status_code==403
    r=w['client'].post(f'{BASE}/challenges/{c["id"]}/duels/{did}/accept',headers=w['accounts'][2][1],json={});assert r.status_code==200,r.text
    assert w['db'].query(ChallengeDuelSeat).count()==2
    assert w['client'].post(f'{BASE}/challenges/{c["id"]}/duels',headers=w['accounts'][3][1],json={'invitee_id':uid}).status_code==409
    own=w['client'].get(f'{BASE}/challenges/{c["id"]}/results',headers=headers).json()
    assert own['total']==1 and own['data'][0]['participant']['user_id']==w['accounts'][1][0]
    finalize(w,'duels')
    by_user={a.user_id:a.points for a in w['db'].query(ChallengeAward)}
    assert by_user[w['accounts'][1][0]]==by_user[w['accounts'][2][0]]==2
    assert by_user[w['accounts'][3][0]]==0


def test_duel_incomplete_unmatched_and_expired_mutations(world):
    w=world;c=publish(w,'duels');assert submit(w,'duels').status_code==200
    r=w['client'].post(f'{BASE}/challenges/{c["id"]}/duels',headers=w['accounts'][1][1],json={'invitee_id':w['accounts'][2][0]});did=r.json()[0]['id']
    assert w['client'].post(f'{BASE}/challenges/{c["id"]}/duels/{did}/accept',headers=w['accounts'][2][1],json={}).status_code==422
    w['clock'][0]=KICKOFF-timedelta(minutes=5)
    assert w['client'].post(f'{BASE}/challenges/{c["id"]}/duels/{did}/decline',headers=w['accounts'][2][1],json={}).status_code==409
    finalize(w,'duels');assert w['db'].query(ChallengeAward).one().points==0


def test_canonical_rollover_preserves_saturday_results_and_history(world):
    w=world;publish(w,'lock');assert submit(w,'lock').status_code==200;finalize(w,'lock')
    headers=w['accounts'][1][1]
    for now in [datetime(2026,9,6,18,tzinfo=timezone.utc),datetime(2026,9,8,20,tzinfo=timezone.utc)]:
        w['clock'][0]=now
        for _ in range(2):
            current=w['client'].get(f'{BASE}/current',headers=headers).json()
            assert current['id']==w['round']['id'] and current['challenges'][3]['state'].startswith('Closed')
    w['clock'][0]=datetime(2026,9,9,4,tzinfo=timezone.utc)
    new=w['client'].get(f'{BASE}/current',headers=headers).json()
    assert new['week']==2 and new['id']!=w['round']['id'] and new['state']=='Upcoming'
    assert all(c['entry'] is None for c in new['challenges'])
    assert w['db'].query(ChallengeEntry).count()==w['db'].query(ChallengeAward).count()==1
    old=w['client'].get(f'{BASE}/rounds/{w["round"]["id"]}',headers=headers).json()
    assert old['challenges'][3]['entry']['status']=='submitted'
    svc.settle(w['db'],svc.challenge_or_404(w['db'],w['challenges']['lock']['id'],lock=True),force=True)
    assert w['client'].get(f'{BASE}/current',headers=headers).json()['id']==new['id']


def test_shared_calendar_dst_and_tuesday_review_boundary():
    # Monday through the first eight hours of Tuesday still names the same
    # matchup. Applying the review offset twice must never move backward.
    for hour, minute in [(3, 59), (4, 0), (11, 59), (12, 0), (23, 59)]:
        assert calendar_matchup_display_week(2026,datetime(2026,9,15,hour,minute,tzinfo=timezone.utc))==2
    assert calendar_matchup_display_week(2026,datetime(2026,9,8,23,tzinfo=timezone.utc))==1
    assert calendar_matchup_display_week(2026,datetime(2026,9,9,3,59,tzinfo=timezone.utc))==1
    assert calendar_matchup_display_week(2026,datetime(2026,9,9,4,tzinfo=timezone.utc))==2
    assert matchup_display_rollover_at(2026,10).hour==5  # Eastern standard time after Nov 1


def test_cancel_withdraws_awards_without_deleting_audit(world):
    w=world;c=publish(w,'lock');submit(w,'lock');finalize(w,'lock')
    r=w['client'].post(f'{ADMIN}/challenges/{c["id"]}/cancel',headers=w['accounts'][0][1],json={'expected_version':c['version'],'reason':'Source game was invalid'})
    assert r.status_code==200 and r.json()['state']=='Canceled'
    assert w['db'].query(ChallengeAward).one().points==0
    assert w['db'].query(ChallengeEntry).count()==1 and w['db'].query(ChallengeAudit).count()>=4


def test_rank_entire_population_before_top10_and_own_rank(world):
    w=world;c=publish(w,'lock');finalize(w,'lock')
    for i in range(15):
        u=User(email=f'leader{i}@example.com',first_name=f'Leader {i}',password_hash='unused',api_token=f'leader-test-{i}',is_active=True)
        w['db'].add(u);w['db'].flush()
        e=ChallengeEntry(challenge_id=c['id'],user_id=u.id,status='submitted',selections=picks(w,'lock'),revision=1)
        w['db'].add(e);w['db'].flush()
        w['db'].add(ChallengeAward(entry_id=e.id,round_id=w['round']['id'],user_id=u.id,points=15-i,source_hash='fixture',revision=1))
    mine=ChallengeEntry(challenge_id=c['id'],user_id=w['accounts'][1][0],status='submitted',selections=picks(w,'lock'),revision=1)
    w['db'].add(mine);w['db'].flush();w['db'].add(ChallengeAward(entry_id=mine.id,round_id=w['round']['id'],user_id=mine.user_id,points=1,source_hash='fixture',revision=1));w['db'].commit()
    r=w['client'].get(f'{BASE}/leaderboard?season=2026&round_id={w["round"]["id"]}',headers=w['accounts'][1][1])
    assert r.status_code==200,r.text
    value=r.json();assert len(value['data'])==10 and value['your_rank']['rank']==15
    assert value['your_rank']['points']==1 and value['provisional']
    assert value['week']==1
    assert [(row['display_name'],row['points']) for row in value['data']]==[(f'Leader {i}',15-i) for i in range(10)]
    top_user=w['db'].get(User,value['data'][0]['user_id']);top_user.first_name='Updated Leader';w['db'].commit()
    refreshed=w['client'].get(f'{BASE}/leaderboard?season=2026&round_id={w["round"]["id"]}',headers=w['accounts'][1][1]).json()
    assert refreshed['data'][0]['display_name']=='Updated Leader'
    w['clock'][0]=datetime(2026,9,9,4,tzinfo=timezone.utc)
    current=w['client'].get(f'{BASE}/current',headers=w['accounts'][1][1]).json()
    fresh=w['client'].get(f'{BASE}/leaderboard?season=2026&round_id={current["id"]}',headers=w['accounts'][1][1]).json()
    assert fresh['week']==2 and fresh['data']==[] and fresh['your_rank'] is None
    assert w['client'].get(f'{BASE}/leaderboard?season=2026',headers=w['accounts'][1][1]).json()['data'][0]['points']==15
    assert 'email' not in str(value)


@pytest.mark.skipif(engine.dialect.name!='postgresql',reason='Requires disposable PostgreSQL row locks')
def test_concurrent_official_submissions_have_one_winner(world):
    w=world;c=publish(w,'lock');barrier=Barrier(2);uid=w['accounts'][1][0]
    payload=EntryWrite(expected_revision=0,selections=picks(w,'lock'))
    def request(_):
        with TestingSessionLocal() as db:
            user=db.get(User,uid);barrier.wait(timeout=10)
            try:
                entry=svc.save_entry(db,svc.challenge_or_404(db,c['id'],lock=True),user,payload)
                return entry.revision
            except HTTPException as e:
                db.rollback();return e.detail['code']
    with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(request,range(2)))
    assert sorted(map(str,values))==['1','VERSION_CONFLICT']
    assert w['db'].query(ChallengeEntry).count()==1


def test_fantasy_competition_ranks_and_field_wide_correction(world):
    w=world;publish(w,'fantasy5')
    for uid in (0,1,2,3):
        selected=picks(w,'fantasy5')
        if uid in (0,1,2):selected[0]['player_id']=w['players'][5].id
        if uid==0:selected[2]['player_id']=w['players'][6].id
        assert submit(w,'fantasy5',user=uid,selections=selected).status_code==200
    for i,p in enumerate(w['players']):
        w['db'].add(PlayerGameStat(player_id=p.id,game_id=w['games'][0].id,season=2026,week=1,source='espn_final_boxscore',stats={'rush_yards':30 if i>=5 else 10}))
    w['db'].commit();finalize(w,'fantasy5')
    rows=w['db'].query(ChallengeScore).order_by(ChallengeScore.entry_id).all()
    assert [s.rank for s in rows]==[1,2,2,4]
    assert [a.points for a in w['db'].query(ChallengeAward).order_by(ChallengeAward.entry_id)]==[10,9,9,7]
    fact=w['db'].query(PlayerGameStat).filter_by(player_id=w['players'][0].id).one();fact.stats={'rush_yards':100};w['db'].commit()
    svc.settle(w['db'],svc.challenge_or_404(w['db'],w['challenges']['fantasy5']['id'],lock=True))
    assert [a.points for a in w['db'].query(ChallengeAward).order_by(ChallengeAward.entry_id)]==[9,8,8,10]
    assert w['db'].query(ChallengeAward).count()==4


def test_confirmed_zero_box_scores_are_not_missing_stats(world):
    w=world;publish(w,'fantasy5');assert submit(w,'fantasy5').status_code==200
    for p in w['players']:
        w['db'].add(PlayerGameStat(player_id=p.id,game_id=w['games'][0].id,season=2026,week=1,source='espn_final_boxscore',stats={'rush_yards':0,'receptions':0}))
    w['db'].commit();assert finalize(w,'fantasy5')=='final'
    assert w['db'].query(ChallengeScore).one().raw_points==0
    assert w['db'].query(ChallengeAward).one().points==10


def test_account_switch_precondition_and_invalid_attempt_rate_limit(world):
    w=world;publish(w,'lock')
    headers={**w['accounts'][1][1], 'X-CFFB-Challenge-Account':str(w['accounts'][2][0])}
    r=w['client'].put(f'{BASE}/challenges/{w["challenges"]["lock"]["id"]}/entry',headers=headers,json={'expected_revision':0,'selections':picks(w,'lock')})
    assert r.status_code==409 and w['db'].query(ChallengeEntry).count()==0
    for _ in range(60):assert submit(w,'lock',selections=[]).status_code==422
    assert submit(w,'lock',selections=[]).status_code==429


def test_final_awards_weekly_and_season_separation(world):
    w=world;c=publish(w,'lock');submit(w,'lock');finalize(w,'lock')
    uid=w['accounts'][1][0]
    for season,week,points in [(2026,2,5),(2025,1,15)]:
        r=svc.ensure_round(w['db'],season,week);w['db'].flush()
        ch=w['db'].query(WeeklyChallenge).filter_by(round_id=r.id,kind='lock').one();ch.status='final'
        e=ChallengeEntry(challenge_id=ch.id,user_id=uid,status='submitted',revision=1,selections=[]);w['db'].add(e);w['db'].flush()
        w['db'].add(ChallengeAward(entry_id=e.id,user_id=uid,round_id=r.id,points=points,source_hash='fixture',revision=1))
    w['db'].commit();headers=w['accounts'][1][1]
    weekly=w['client'].get(f'{BASE}/leaderboard?season=2026&round_id={w["round"]["id"]}',headers=headers).json()
    season=w['client'].get(f'{BASE}/leaderboard?season=2026',headers=headers).json()
    assert weekly['data'][0]['points']==5 and season['data'][0]['points']==10
    assert not season['provisional']


def test_database_constraints_for_entries_and_duel_seats(world):
    w=world;c=publish(w,'lock');submit(w,'lock')
    with pytest.raises(IntegrityError):
        with w['db'].begin_nested():
            w['db'].add(ChallengeEntry(challenge_id=c['id'],user_id=w['accounts'][1][0],selections=[],revision=1));w['db'].flush()


@pytest.mark.skipif(engine.dialect.name!='postgresql',reason='Requires disposable PostgreSQL row locks')
def test_simultaneous_duel_accepts_across_inviter_invitee_roles(world):
    w=world;c=publish(w,'duels')
    for i in (1,2,3):assert submit(w,'duels',user=i).status_code==200
    with TestingSessionLocal() as db:
        a=svc.invite_duel(db,svc.challenge_or_404(db,c['id'],lock=True),db.get(User,w['accounts'][1][0]),w['accounts'][2][0]);first=a.id
        b=svc.invite_duel(db,svc.challenge_or_404(db,c['id'],lock=True),db.get(User,w['accounts'][3][0]),w['accounts'][1][0]);second=b.id
    barrier=Barrier(2)
    def accept(args):
        uid,did=args
        with TestingSessionLocal() as db:
            u=db.get(User,uid);barrier.wait(timeout=10)
            try:
                svc.respond_duel(db,svc.challenge_or_404(db,c['id'],lock=True),u,did,True);return 'accepted'
            except HTTPException as e:db.rollback();return e.detail['code']
    with ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(accept,[(w['accounts'][2][0],first),(w['accounts'][1][0],second)]))
    assert sorted(values)==['DUPLICATE_DUEL','accepted']
    assert w['db'].query(ChallengeDuel).filter_by(status='accepted').count()==1
    assert w['db'].query(ChallengeDuelSeat).count()==2


def test_reviewed_dnp_zero_and_newer_full_report_withdraws_it(world):
    from collegefootballfantasy_api.app.models.player_availability_event import PlayerAvailabilityEvent
    w=world;publish(w,'fantasy5');submit(w,'fantasy5')
    for p in w['players'][1:]:w['db'].add(PlayerGameStat(player_id=p.id,game_id=w['games'][0].id,season=2026,week=1,source='espn_final_boxscore',stats={'rush_yards':10}))
    w['db'].add(PlayerAvailabilityEvent(player_id=w['players'][0].id,season=2026,week=1,status='OUT',effective_from_week=1,effective_until_week=1,reviewed=True,source='official_report'))
    w['db'].commit();assert finalize(w,'fantasy5')=='final'
    assert w['db'].query(ChallengeScore).one().raw_points==4
    w['db'].add(PlayerAvailabilityEvent(player_id=w['players'][0].id,season=2026,week=1,status='FULL',effective_from_week=1,effective_until_week=1,reviewed=True,source='official_report'))
    w['db'].commit();assert svc.settle(w['db'],svc.challenge_or_404(w['db'],w['challenges']['fantasy5']['id'],lock=True))=='processing'
    assert w['db'].query(ChallengeAward).one().points==0


def test_pregame_delay_does_not_close_the_challenge_before_its_deadline(world):
    w=world;publish(w,'lock');w['games'][0].schedule_status='delayed';w['db'].commit()
    assert submit(w,'lock').status_code==200


def test_next_week_may_be_published_but_remains_upcoming_until_rollover(world):
    w=world
    r=svc.ensure_round(w['db'],2026,2);w['db'].commit()
    c=w['db'].query(WeeklyChallenge).filter_by(round_id=r.id,kind='lock').one()
    game=Game(external_id='next-week-fixture',season=2026,week=2,season_type='regular',schedule_status='scheduled',start_date=KICKOFF+timedelta(days=7),home_team='Next Home',away_team='Next Away')
    w['db'].add(game);w['db'].commit()
    from collegefootballfantasy_api.app.schemas.weekly_challenge import ChallengeConfig
    svc.configure(w['db'],c,ChallengeConfig(expected_version=0,game_ids=[game.id]),w['accounts'][0][0]);svc.publish(w['db'],c,1,w['accounts'][0][0])
    detail=w['client'].get(f'{BASE}/challenges/{c.id}',headers=w['accounts'][1][1]).json()
    assert detail['state']=='Upcoming'
    w['clock'][0]=datetime(2026,9,9,4,tzinfo=timezone.utc)
    assert w['client'].get(f'{BASE}/challenges/{c.id}',headers=w['accounts'][1][1]).json()['state']=='Open'
    submitted=w['client'].put(f'{BASE}/challenges/{c.id}/entry',headers=w['accounts'][1][1],json={'expected_revision':0,'submit':True,'selections':[{'game_id':game.id,'team':game.home_team}]})
    assert submitted.status_code==200,submitted.text


def test_expired_future_slate_never_opens_at_rollover(world):
    w=world;r=svc.ensure_round(w['db'],2026,2);w['db'].commit()
    c=w['db'].query(WeeklyChallenge).filter_by(round_id=r.id,kind='lock').one()
    game=Game(external_id='early-next-week',season=2026,week=2,season_type='regular',schedule_status='scheduled',start_date=datetime(2026,9,8,16,tzinfo=timezone.utc),home_team='Next Home',away_team='Next Away')
    w['db'].add(game);w['db'].commit()
    from collegefootballfantasy_api.app.schemas.weekly_challenge import ChallengeConfig
    svc.configure(w['db'],c,ChallengeConfig(expected_version=0,game_ids=[game.id]),w['accounts'][0][0]);svc.publish(w['db'],c,1,w['accounts'][0][0])
    w['clock'][0]=datetime(2026,9,9,4,tzinfo=timezone.utc)
    assert w['client'].get(f'{BASE}/challenges/{c.id}',headers=w['accounts'][1][1]).json()['state'].startswith('Closed')


def test_save_draft_cannot_silently_change_an_already_official_entry(world):
    w=world;publish(w,'lock');r=submit(w,'lock');assert r.status_code==200
    changed=[{'game_id':w['games'][0].id,'team':w['games'][0].away_team}]
    r=submit(w,'lock',expected_revision=1,submit=False,selections=changed)
    assert r.status_code==422
    e=w['db'].query(ChallengeEntry).one();assert e.selections==picks(w,'lock') and e.revision==1


def test_identity_correction_invalidates_a_previously_final_award(world):
    w=world;publish(w,'lock');submit(w,'lock');finalize(w,'lock')
    assert w['db'].query(ChallengeAward).one().points==5
    w['games'][0].external_id='different-provider-event';w['db'].commit()
    assert svc.settle(w['db'],svc.challenge_or_404(w['db'],w['challenges']['lock']['id'],lock=True))=='processing'
    assert w['db'].query(ChallengeAward).one().points==0


def test_post_rollover_void_cannot_resurrect_when_late_game_finishes(world):
    w=world;publish(w,'lock');submit(w,'lock')
    g=w['games'][0];g.start_date=matchup_display_rollover_at(2026,1)+timedelta(days=1)
    assert finalize(w,'lock',status='postponed')=='no_contest'
    g.schedule_status='final';g.home_points=40;g.away_points=10;g.start_date=KICKOFF
    w['db'].commit()
    assert svc.settle(w['db'],svc.challenge_or_404(w['db'],w['challenges']['lock']['id'],lock=True))=='no_contest'
    assert w['db'].query(ChallengeAward).one().points==0
    assert w['db'].query(ChallengeRecognition).filter_by(active=True).count()==0


def test_fantasy_pool_excludes_provider_only_and_retired_players_and_dedupes_sheet_games(world):
    w=world
    w['db'].add_all([
        Player(name='Historical Provider Only',school='Alabama',position='QB',sheet_projected_season_points=100),
        Player(name='Retired Canonical',school='Alabama',position='RB',sheet_projected_season_points=100,sheet_source_sheet_id='legacy-canonical-preseason:2026:old'),
        Player(name='Unapproved School',school='FIU',position='WR',sheet_projected_season_points=100,sheet_source_sheet_id='canonical-correction:2026:test'),
        Game(external_id='sheet-duplicate',season=2026,week=1,season_type='regular',schedule_status='scheduled',start_date=KICKOFF,home_team=w['games'][0].home_team,away_team=w['games'][0].away_team),
    ])
    w['db'].commit();value=svc.catalog(w['db'],2026,1)
    assert {p['id'] for p in value['players']}=={p.id for p in w['players']}
    assert len(value['games'])==12
    assert all(p['game_id']==w['games'][0].id for p in value['players'])


def test_publishing_cannot_bypass_canonical_game_deduplication(world):
    w=world;g=w['games'][0]
    duplicate=Game(external_id=g.external_id,season=g.season,week=g.week,season_type='regular',schedule_status='scheduled',start_date=g.start_date,home_team=g.home_team,away_team=g.away_team)
    w['db'].add(duplicate);w['db'].commit()
    c=w['db'].query(WeeklyChallenge).filter_by(round_id=w['round']['id'],kind='slate12').one()
    config={'game_ids':[duplicate.id]+[x.id for x in w['games'][:11]],'featured_game_id':g.id,'player_ids':[],'underdogs':[]}
    blockers,_=svc.validate_config(w['db'],c,config)
    assert any('canonical weekly game catalog' in text for text in blockers)


def test_unselectable_games_cannot_set_an_invisible_deadline_or_avoid_no_contest(world):
    w=world;ids=[g.id for g in w['games'][:2]]
    c=w['db'].query(WeeklyChallenge).filter_by(round_id=w['round']['id'],kind='fantasy5').one()
    blockers,_=svc.validate_config(w['db'],c,{'game_ids':ids,'player_ids':[p.id for p in w['players']]})
    assert any('supply at least one eligible' in text for text in blockers)
    c=w['db'].query(WeeklyChallenge).filter_by(round_id=w['round']['id'],kind='upset').one()
    blockers,_=svc.validate_config(w['db'],c,{'game_ids':[g.id for g in w['games'][:4]],'underdogs':[{'game_id':g.id,'team':g.away_team,'points':1} for g in w['games'][:3]]})
    assert any('explicitly designated underdog' in text for text in blockers)


@pytest.mark.parametrize('kind', list(svc.KINDS))
def test_every_format_rejects_wrong_count_without_mutating_an_official_entry(world, kind):
    w = world
    changes = {}
    # More eligible options than permitted picks reproduces the real Upset Hunter slate.
    if kind in {'upset', 'lock'}:
        games = w['games'][:6]
        changes['game_ids'] = [g.id for g in games]
        if kind == 'upset':
            changes['underdogs'] = [{'game_id': g.id, 'team': g.away_team, 'points': 2} for g in games]
    publish(w, kind, **changes)
    original = submit(w, kind)
    assert original.status_code == 200, original.text
    original = original.json()
    selected = picks(w, kind)
    too_many = selected + ([{'player_id': w['players'][5].id, 'slot': 'QB'}] if kind == 'fantasy5' else [
        {'game_id': w['games'][len(selected)].id, 'team': w['games'][len(selected)].away_team if kind == 'upset' else w['games'][len(selected)].home_team}
    ] if len(selected) < 12 else [selected[0]])
    for submit_flag, choices in [(True, selected[:-1]), (True, too_many), (False, too_many)]:
        rejected = submit(w, kind, expected_revision=1, submit=submit_flag, selections=choices)
        assert rejected.status_code == 422, rejected.text
        stored = w['client'].get(f'{BASE}/challenges/{w["challenges"][kind]["id"]}/entry', headers=w['accounts'][1][1]).json()
        assert stored == original
    # A partial entry is permitted only as an explicit draft, never as official.
    draft = submit(w, kind, user=2, submit=False, selections=selected[:-1])
    assert draft.status_code == 200 and draft.json()['status'] == 'draft', draft.text
    rejected = submit(w, kind, user=2, expected_revision=1, selections=selected[:-1])
    assert rejected.status_code == 422, rejected.text
    assert w['db'].query(ChallengeEntry).filter_by(user_id=w['accounts'][2][0]).one().status == 'draft'


def test_public_launch_round_is_server_controlled_and_advances_after_launch(world, monkeypatch):
    w=world
    monkeypatch.setattr(svc.settings,'weekly_challenges_launch_season',2026)
    monkeypatch.setattr(svc.settings,'weekly_challenges_launch_week',2)
    r=svc.ensure_round(w['db'],2026,2);w['db'].commit()
    c=w['db'].query(WeeklyChallenge).filter_by(round_id=r.id,kind='lock').one()
    game=Game(external_id='launch-round-fixture',season=2026,week=2,season_type='regular',schedule_status='scheduled',start_date=KICKOFF+timedelta(days=7),home_team='Launch Home',away_team='Launch Away')
    w['db'].add(game);w['db'].commit()
    from collegefootballfantasy_api.app.schemas.weekly_challenge import ChallengeConfig
    svc.configure(w['db'],c,ChallengeConfig(expected_version=0,game_ids=[game.id]),w['accounts'][0][0]);svc.publish(w['db'],c,1,w['accounts'][0][0])
    current=w['client'].get(f'{BASE}/current',headers=w['accounts'][1][1]).json()
    assert current['week']==2 and current['state']=='Open'
    assert w['client'].get(f'{BASE}/challenges/{c.id}',headers=w['accounts'][1][1]).json()['state']=='Open'
    submitted=w['client'].put(f'{BASE}/challenges/{c.id}/entry',headers=w['accounts'][1][1],json={'expected_revision':0,'submit':True,'selections':[{'game_id':game.id,'team':game.home_team}]})
    assert submitted.status_code==200,submitted.text
    w['clock'][0]=datetime(2026,9,16,4,tzinfo=timezone.utc)
    assert w['client'].get(f'{BASE}/current',headers=w['accounts'][1][1]).json()['week']==3
    assert svc.competition_week(2027,datetime(2027,9,1,tzinfo=timezone.utc))==1
