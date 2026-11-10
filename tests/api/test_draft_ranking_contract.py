"""Ranking validity, full-catalog policy preservation and stable ordering."""
import json
from pathlib import Path
import pytest
from collegefootballfantasy_api.app.services.draft_rankings import build_master_draft_board,source_rank
from collegefootballfantasy_api.app.models.player import Player

CONFIG={'leagueSize':12,'totalRosterSpots':13,'rosterSlots':{'QB':1,'RB':2,'WR':2,'TE':1,'K':1,'BE':5,'IR':0}}

def p(id,position='WR',points=100,source=10):
    return {'id':id,'name':f'Player {id}','school':'Texas','pos':position,'rank':source,'sheetProjectedSeasonPoints':points,'status':'HEALTHY','projection':{'floor':0,'ceiling':0,'expectedPlays':0}}


def test_public_catalog_model_weights_and_talent_are_preserved_without_name_hardcodes():
    ref=json.loads((Path(__file__).resolve().parents[1]/'fixtures/draft_master_policy_reference.json').read_text())
    board=build_master_draft_board(ref['players'],ref['config'])
    assert len(board)==815
    assert len({r['id'] for r in board})==815
    for row in board:
        expected=ref['expected'][str(row['id'])]
        assert row['cfb27Overall']==expected['cfb27Overall']
        assert row['cfb27TalentScore']==expected['cfb27TalentScore']
        assert abs(row['finalDraftScore']-expected['finalDraftScore'])<=.001  # deterministic ID ties replace input-order ties
    trent=next(row for row in board if row['id']==1881)
    assert trent['sourceBoardRank'] is None
    assert trent['masterDraftRank']>811
    assert trent['projectedPoints']==245.5
    assert all(row['sourceBoardRank'] is not None for row in board[:811])


@pytest.mark.parametrize('invalid',[None,'',0,-1,float('nan'),float('inf'),True,'unknown'])
def test_missing_rank_cannot_receive_top_priority_even_with_extreme_projection(invalid):
    rows=[p(1,points=10,source='2'),p(2,points=10000,source=invalid)]
    assert [r['id'] for r in build_master_draft_board(rows,CONFIG)]==[1,2]
    assert source_rank({'restOfSeasonRank':2,'posRank':1}) is None


def test_projection_zero_missing_ties_and_duplicate_names_preserve_identity():
    rows=[p(1,points=20),p(2,points=20),p(3,points=0),p(4,points=None)]
    rows[0]['name']=rows[1]['name']='Same Name'
    board=build_master_draft_board(rows,CONFIG)
    assert len(board)==4 and len({r['id'] for r in board})==4
    assert next(r for r in board if r['id']==3)['projectedPoints']==0
    assert next(r for r in board if r['id']==4)['projectedPoints'] is None
    assert [r['id'] for r in board]==[r['id'] for r in build_master_draft_board(list(reversed(rows)),CONFIG)]


def test_kicker_floor_quarterback_depth_and_editorial_rules_keep_existing_policy():
    rows=[p(i,'RB',300-i,source=i) for i in range(1,80)]+[p(i,'WR',300-i,source=i) for i in range(80,140)]+[p(200+i,'QB',300-i,source=200+i) for i in range(40)]+[p(300,'K',200,source=300)]
    board=build_master_draft_board(rows,CONFIG)
    assert next(r for r in board if r['id']==300)['masterDraftRank']>=100
    assert sum(r['pos']=='QB' for r in board[:72])<=14


def test_missouri_review_moves_hardy_down_and_roberts_up_without_changing_forecasts():
    from copy import deepcopy
    ref=json.loads((Path(__file__).resolve().parents[1]/'fixtures/draft_master_policy_reference.json').read_text())
    original=deepcopy(ref['players'])
    baseline=build_master_draft_board(ref['players'],ref['config'],season=2027)
    reviewed=build_master_draft_board(ref['players'],ref['config'],season=2026)
    assert ref['players']==original
    assert len(reviewed)==815 and len({r['id'] for r in reviewed})==815
    assert sorted(r['masterDraftRank'] for r in reviewed)==list(range(1,816))
    rbs=[r for r in reviewed if r['pos']=='RB']
    hardy=next(r for r in reviewed if r['name']=='Ahmad Hardy' and r['school']=='Missouri')
    roberts=next(r for r in reviewed if r['name']=='Jamal Roberts' and r['school']=='Missouri')
    assert rbs.index(hardy)+1>=60
    assert rbs.index(roberts)+1<=15
    assert roberts['masterDraftRank']<hardy['masterDraftRank']
    by_id={r['id']:r for r in baseline}
    for row in reviewed:
        for field in ('projectedPoints','sourceBoardRank','adp','cfb27Overall','cfb27TalentScore','finalDraftScore'):
            assert row[field]==by_id[row['id']][field]
    assert [(i,r['id']) for i,r in enumerate(reviewed) if r['pos']!='RB']==[(i,r['id']) for i,r in enumerate(baseline) if r['pos']!='RB']
    moved={hardy['id'],roberts['id']}
    assert [r['id'] for r in reviewed if r['pos']=='RB' and r['id'] not in moved]==[r['id'] for r in baseline if r['pos']=='RB' and r['id'] not in moved]
    assert [r['id'] for r in reviewed]==[r['id'] for r in build_master_draft_board(list(reversed(ref['players'])),ref['config'],season=2026)]


@pytest.mark.parametrize('season,school,source',[(2027,'Missouri',1),(2026,'Texas',1),(2026,'Missouri',None)])
def test_missouri_review_does_not_follow_transfers_future_seasons_or_promote_unranked(season,school,source):
    rows=[p(i,'RB',300-i,source=i) for i in range(1,90)]
    rows[0].update(name='Ahmad Hardy',school=school,rank=source)
    rows[-1].update(name='Jamal Roberts',school=school,rank=source)
    baseline=build_master_draft_board(rows,CONFIG)
    reviewed=build_master_draft_board(rows,CONFIG,season=season)
    assert [r['id'] for r in reviewed]==[r['id'] for r in baseline]


def test_missouri_review_handles_small_conference_pool_and_ambiguous_names():
    rows=[p(1,'RB',300,1),p(2,'RB',50,2)]
    rows[0].update(name='Ahmad Hardy',school='Missouri')
    rows[1].update(name='Jamal Roberts',school='Missouri')
    assert [r['id'] for r in build_master_draft_board(rows,CONFIG,season=2026)]==[2,1]
    rows.append({**rows[0],'id':3})
    without_roberts=[r for r in rows if r['id']!=2]
    assert [r['id'] for r in build_master_draft_board(without_roberts,CONFIG,season=2026)]==[1,3]


def test_global_sort_filter_pagination_rank_labels_and_invalid_adp(client,db_session):
    players=[Player(name=f'Rank {adp}',position='WR',school='Texas',sheet_adp=adp,cfb27_rank=index+1,sheet_projected_season_points=100+index,sheet_source_sheet_id='canonical-preseason:2026:ranking-test') for index,adp in enumerate([119,20,10,2,0,None])]
    db_session.add_all(players);db_session.commit()
    first=client.get('/players',params={'draft_eligible':True,'sort':'adp','limit':2}).json()
    second=client.get('/players',params={'draft_eligible':True,'sort':'adp','offset':2,'limit':2}).json()
    assert [r['sheet_adp'] for r in first['data']+second['data']]==[2,10,20,119]
    assert first['ranking_version']==second['ranking_version']
    full=client.get('/players',params={'draft_eligible':True,'sort':'draft_rank','limit':100}).json()
    filtered=client.get('/players',params={'draft_eligible':True,'sort':'draft_rank','position':'WR','search':'Rank 10'}).json()
    assert len(filtered['data'])==1
    assert filtered['data'][0]['master_draft_rank']==next(r['master_draft_rank'] for r in full['data'] if r['id']==filtered['data'][0]['id'])


@pytest.mark.parametrize('config',[{'leagueSize':12.1},{'leagueSize':True},{'rosterSlots':{'BAD':1}},{'totalRosterSpots':False},{'unexpected':1}])
def test_rejects_malformed_ranking_context_before_computation(client,config):
    response=client.get('/players',params={'draft_eligible':True,'draft_config':json.dumps(config)})
    assert response.status_code==422


def test_full_master_pool_autopick_searches_after_first_500_illegal_positions(db_session,monkeypatch):
    from types import SimpleNamespace
    from collegefootballfantasy_api.app.models.league import League
    from collegefootballfantasy_api.app.models.team import Team
    from collegefootballfantasy_api.app.models.user import User
    from collegefootballfantasy_api.app.models.draft import Draft
    from collegefootballfantasy_api.app.services.draft_service import _select_auto_pick_player
    from collegefootballfantasy_api.app.services import draft_rankings
    user=User(email='ranking-pool@example.com',first_name='Rank',password_hash='test',api_token='rank-token');db_session.add(user);db_session.flush()
    league=League(name='Full ranking pool',commissioner_user_id=user.id,season_year=2026,max_teams=2);db_session.add(league);db_session.flush()
    team=Team(league_id=league.id,owner_user_id=user.id,name='One');db_session.add(team)
    draft=Draft(league_id=league.id,current_pick_number=1,status='on_clock',draft_datetime_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc));db_session.add(draft);db_session.flush()
    candidates={i:SimpleNamespace(id=i,position='QB' if i<=600 else 'WR') for i in range(1,602)}
    board={i:{'id':i,'masterDraftRank':i} for i in candidates}
    monkeypatch.setattr(draft_rankings,'build_draft_ranking_snapshot',lambda *a,**k:{'board':board,'players':candidates})
    selected=_select_auto_pick_player(db_session,league=league,draft_row=draft,team=team,settings_row=SimpleNamespace(roster_slots_json={'WR':1},superflex_enabled=False))
    assert selected.id==601


def test_season_only_projection_is_not_inflated_and_missing_is_not_zero(db_session):
    from collegefootballfantasy_api.app.services.draft_board_outlook import build_rest_of_season_draft_board, _fallback_weekly_projection
    rows=[Player(name='Forecast Source',position='WR',school='Texas',sheet_source_sheet_id='canonical-preseason:2026:test',sheet_projected_season_points=245.5),Player(name='Zero Source',position='WR',school='Texas',sheet_source_sheet_id='canonical-preseason:2026:test',sheet_projected_season_points=0),Player(name='Missing Source',position='WR',school='Texas',sheet_source_sheet_id='canonical-preseason:2026:test')]
    db_session.add_all(rows);db_session.commit()
    board=build_rest_of_season_draft_board(db_session,season=2026)
    assert board[rows[0].id].projected_points==245.5
    assert board[rows[1].id].projected_points==0
    assert rows[2].id not in board  # missing preseason inputs remain outside the reviewed draft pool
    assert _fallback_weekly_projection(rows[2]) is None
    for invalid in [None,'',True,float('nan'),float('inf'),-1]:
        assert _fallback_weekly_projection(type('Source',(),{'sheet_projected_season_points':invalid})()) is None


def test_real_mock_same_settings_share_order_and_refresh_after_source_change(client,db_session):
    from collegefootballfantasy_api.app.models.league import League
    from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
    from collegefootballfantasy_api.app.models.user import User
    from collegefootballfantasy_api.app.services.draft_rankings import build_draft_ranking_snapshot,DEFAULT_SLOTS
    from collegefootballfantasy_api.app.services.league_flow import FIXED_ROSTER_SLOTS
    user=User(email='ranking-parity@example.com',first_name='Rank',password_hash='test',api_token='parity-token');db_session.add(user);db_session.flush()
    league=League(name='Parity',commissioner_user_id=user.id,season_year=2026,max_teams=12);db_session.add(league);db_session.flush()
    settings=LeagueSettings(league_id=league.id,roster_slots_json=FIXED_ROSTER_SLOTS);db_session.add(settings)
    rows=[Player(name=f'Parity {pos}',position=pos,school='Texas',cfb27_rank=i+1,sheet_projected_season_points=300-i*30,sheet_source_sheet_id='canonical-preseason:2026:test') for i,pos in enumerate(['QB','RB','WR','TE','K'])]
    db_session.add_all(rows);db_session.commit()
    real=build_draft_ranking_snapshot(db_session,season=2026,league_id=league.id)
    mock=build_draft_ranking_snapshot(db_session,season=2026,config={'leagueSize':12,'totalRosterSpots':13,'rosterSlots':DEFAULT_SLOTS})
    assert real['config']==mock['config']
    assert real['version']==mock['version']
    assert [r['id'] for r in real['board'].values()]==[r['id'] for r in mock['board'].values()]
    old=real['version'];rows[2].sheet_projected_season_points=700;db_session.commit()
    refreshed=build_draft_ranking_snapshot(db_session,season=2026,league_id=league.id)
    assert refreshed['version']!=old
    assert refreshed['board'][rows[2].id]['projectedPoints']==700
    settings.conference_codes=['BIG10'];db_session.commit()
    assert build_draft_ranking_snapshot(db_session,season=2026,league_id=league.id)['board']=={}
    settings.conference_codes=['SEC'];settings.scoring_json={'offense':{'rec_yards':1.0,'receptions':2.0,'rec_tds':10.0}};rows[2].sheet_projection_stats={'receptions':10,'rec_yards':100,'rec_tds':1};db_session.commit()
    custom=build_draft_ranking_snapshot(db_session,season=2026,league_id=league.id)
    assert custom['version']!=refreshed['version']
    assert custom['board'][rows[2].id]['projectedPoints']!=700
    response=client.get('/players',params={'draft_eligible':True,'sort':'projected_points','limit':100}).json()
    assert isinstance(response['ranking_week'],int)
    assert [row['draft_projected_points'] for row in response['data']]==sorted([row['draft_projected_points'] for row in response['data']],reverse=True)


def test_reviewed_missouri_order_reaches_real_mock_and_filtered_api_without_altering_points(client,db_session):
    from collegefootballfantasy_api.app.models.league import League
    from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
    from collegefootballfantasy_api.app.models.user import User
    from collegefootballfantasy_api.app.services.draft_rankings import build_draft_ranking_snapshot
    from collegefootballfantasy_api.app.services.league_flow import FIXED_ROSTER_SLOTS
    user=User(email='missouri-ranking@example.com',first_name='Rank',password_hash='test',api_token='missouri-token')
    db_session.add(user);db_session.flush()
    league=League(name='Missouri ranking review',commissioner_user_id=user.id,season_year=2026,max_teams=12)
    db_session.add(league);db_session.flush()
    db_session.add(LeagueSettings(league_id=league.id,roster_slots_json=FIXED_ROSTER_SLOTS))
    players=[Player(name=name,school='Missouri',position='RB',cfb27_rank=i+1,sheet_projected_season_points=points,sheet_source_sheet_id='canonical-preseason:2026:test') for i,(name,points) in enumerate([('Ahmad Hardy',300),('Jamal Roberts',100)])]
    db_session.add_all(players);db_session.commit()
    real=build_draft_ranking_snapshot(db_session,season=2026,league_id=league.id)
    mock=build_draft_ranking_snapshot(db_session,season=2026)
    assert real['version']==mock['version']
    assert [r['name'] for r in real['board'].values()]==['Jamal Roberts','Ahmad Hardy']
    params={'season':2026,'draft_eligible':True,'sort':'draft_rank'}
    full=client.get('/players',params=params).json()
    assert [r['name'] for r in full['data']]==['Jamal Roberts','Ahmad Hardy']
    filtered=client.get('/players',params={**params,'search':'Ahmad Hardy','position':'RB'}).json()
    assert filtered['data'][0]['master_draft_rank']==2
    by_points=client.get('/players',params={**params,'sort':'projected_points'}).json()
    assert [r['name'] for r in by_points['data']]==['Ahmad Hardy','Jamal Roberts']
    assert [r['sheet_projected_season_points'] for r in by_points['data']]==[300,100]
    assert [p.cfb27_rank for p in players]==[1,2]


def test_ratings_content_change_invalidates_talent_even_when_mtime_is_preserved(tmp_path,monkeypatch):
    import os
    from collegefootballfantasy_api.app.services import cfb27_player_sync
    source=tmp_path/'ratings.csv'
    source.write_text('TEAM,PLAYER,EA POSITION,OVR\nOhio State,Alpha Example,QB,95\n')
    monkeypatch.setattr(cfb27_player_sync,'CFB27_SOURCE_PATH',source)
    row={**p(1,'QB'), 'name':'Alpha Example','school':'Ohio State'}
    first=build_master_draft_board([row],CONFIG)
    original=source.stat()
    source.write_text('TEAM,PLAYER,EA POSITION,OVR\nOhio State,Alpha Example,QB,90\n')
    os.utime(source,ns=(original.st_atime_ns,original.st_mtime_ns))
    assert source.stat().st_mtime_ns==original.st_mtime_ns
    second=build_master_draft_board([row],CONFIG)
    assert first[0]['cfb27Overall']==95
    assert second[0]['cfb27Overall']==90


def test_mock_conferences_scope_full_ranking_before_search_and_pagination(client, db_session):
    schools = ['Texas', 'Ohio State', 'Arizona', 'Miami', 'Notre Dame', 'Alabama']
    players = [Player(name=f'Mock Pool {i}', school=school, position='WR', sheet_adp=i+1, cfb27_rank=i+1, sheet_projected_season_points=200-i, sheet_source_sheet_id='canonical-preseason:2026:conference-test') for i, school in enumerate(schools)]
    db_session.add_all(players); db_session.commit()
    params = {'draft_eligible': True, 'sort': 'draft_rank', 'conference_codes': 'ACC,SEC,SEC', 'season': 2026}
    full = client.get('/players', params={**params, 'limit': 100}).json()
    assert full['draft_conference_codes'] == ['SEC', 'ACC']
    assert {p['school'] for p in full['data']} == {'Texas', 'Alabama', 'Miami'}
    assert sorted(p['master_draft_rank'] for p in full['data']) == [1, 2, 3]
    pages = [client.get('/players', params={**params, 'limit': 1, 'offset': offset}).json() for offset in range(3)]
    assert all(p['total'] == 3 and p['ranking_version'] == full['ranking_version'] and p['draft_conference_codes'] == ['SEC','ACC'] for p in pages)
    assert [page['data'][0]['id'] for page in pages] == [p['id'] for p in full['data']]
    one = client.get('/players', params={**params, 'search': 'Mock Pool 3'}).json()['data'][0]
    assert one['master_draft_rank'] == next(p['master_draft_rank'] for p in full['data'] if p['id'] == one['id'])
    default = client.get('/players', params={'draft_eligible': True, 'sort':'draft_rank'}).json()
    assert default['total'] == 6
    assert default['ranking_version'] != full['ranking_version']
    independent = client.get('/players', params={**params, 'conference_codes': 'INDEPENDENT'}).json()
    assert [p['school'] for p in independent['data']] == ['Notre Dame']
    alias = client.get('/players', params={**params, 'conference_codes': 'Big Ten'}).json()
    assert [p['school'] for p in alias['data']] == ['Ohio State']


@pytest.mark.parametrize('codes', ['', 'AAC', 'SEC,', 'SEC,FAKE'])
def test_mock_conference_input_never_silently_widens_the_pool(client, codes):
    r = client.get('/players', params={'draft_eligible': True, 'conference_codes': codes})
    assert r.status_code == 422


@pytest.mark.parametrize('extra', [{'draft_eligible': False}, {'draft_eligible': True, 'league_id': 77}])
def test_mock_conferences_cannot_override_real_league_settings(client, extra):
    r = client.get('/players', params={**extra, 'conference_codes': 'SEC'})
    assert r.status_code == 422
