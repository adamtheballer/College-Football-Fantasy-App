from datetime import datetime, timezone
import pytest
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.league import League
from collegefootballfantasy_api.app.models.league_member import LeagueMember
from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
from collegefootballfantasy_api.app.models.team import Team
from collegefootballfantasy_api.app.models.roster import RosterEntry
from collegefootballfantasy_api.app.services import player_rankings
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.scoring import get_scoring_rules


@pytest.fixture(autouse=True)
def completed_clock(monkeypatch):
    monkeypatch.setattr(player_rankings, "calendar_cfb_week", lambda season: 3)


def player(db, name, position="RB", school="Texas"):
    p = Player(name=name, position=position, school=school, sheet_source_sheet_id="canonical-preseason:2026:rank-test",
               sheet_projected_season_points=100, image_url="https://example.com/player.png")
    db.add(p); db.flush(); return p


def game(db, week=2, school="Texas", status="final"):
    g = Game(external_id=f"espn:rank-{school}-{week}", season=2026, week=week, season_type="regular",
             home_team=school, away_team="Oklahoma", schedule_status=status,
             start_date=datetime(2026, 9, 12, 16, tzinfo=timezone.utc))
    db.add(g); db.flush(); return g


def score(db, p, g, stats, source="espn_final_boxscore"):
    db.add(PlayerGameStat(player_id=p.id, game_id=g.id, season=2026, week=g.week, source=source, stats=stats))


def identity(client, suffix="one"):
    r = client.post('/auth/signup', json={'first_name':'Ranks','email':f'rank-{suffix}@example.com','password':'StrongPass123!'})
    assert r.status_code == 201
    return r.json()['user']['id'], {'Authorization': f"Bearer {r.json()['access_token']}"}


def test_home_leaders_use_actual_final_points_not_projection_or_missing_zero(client, db_session, monkeypatch):
    g = game(db_session)
    leader = player(db_session, "Real leader"); zero = player(db_session, "Real zero"); missing = player(db_session, "Missing stats")
    score(db_session, leader, g, {"rush_yards": 120, "rush_tds": 1})
    score(db_session, zero, g, {"rush_yards": 0})
    db_session.add(PlayerStat(player_id=missing.id, season=2026, week=2, verified=True, stats={'fantasy_points':999}))
    db_session.commit()
    monkeypatch.setattr(settings, 'player_headshots_enabled', True)
    r = client.get('/player-rankings/leaders').json()
    assert r['week'] == 2
    rb = next(x for x in r['data'] if x['position'] == 'RB')['player']
    assert rb['name'] == 'Real leader' and rb['fantasy_points'] == 18
    assert rb['image_url'] == 'https://example.com/player.png'
    assert len(r['data']) == 5 and r['pending_players'] == 1
    rows = client.get('/player-rankings').json()['data']
    assert [(r['name'], r['fantasy_points'], r['position_rank']) for r in rows] == [('Real leader',18,1),('Real zero',0,2),('Missing stats',None,None)]


def test_rank_ties_filter_pagination_and_picture_switch(client, db_session, monkeypatch):
    g=game(db_session)
    for name,pos,points in [('A','RB',10),('B','RB',10),('C','RB',5),('D','QB',20)]:
        p=player(db_session,name,pos); score(db_session,p,g,{'fantasy_points':points})
    db_session.commit()
    monkeypatch.setattr(settings,'player_headshots_enabled',False)
    result=client.get('/player-rankings',params={'position':'RB','offset':1,'limit':2}).json()
    assert result['total']==3
    assert [(r['name'],r['position_rank']) for r in result['data']]==[('B',1),('C',3)]
    assert all(r['image_url'] is None for r in result['data'])
    assert all(r['stats'] == {} for r in result['data'])  # FPTS-only facts do not invent zero raw stats.
    assert client.get('/player-rankings',params={'search':'C'}).json()['total']==1
    assert client.get('/player-rankings',params={'limit':101}).status_code==422


def test_live_unverified_and_future_scores_cannot_become_leaders(client, db_session):
    g=game(db_session,status='in'); p=player(db_session,'Live player')
    score(db_session,p,g,{'rush_yards':999})
    future=game(db_session,week=3,school='Alabama'); other=player(db_session,'Future','RB','Alabama')
    score(db_session,other,future,{'rush_yards':9999})
    db_session.commit()
    assert all(r['player'] is None for r in client.get('/player-rankings/leaders').json()['data'])
    assert client.get('/player-rankings',params={'week':3}).status_code==422


def test_week_zero_is_counted_once_in_fantasy_week_one(client, db_session):
    p=player(db_session,'Opening scorer'); opener=game(db_session,week=0); later=game(db_session,week=1)
    opener.start_date=datetime(2026,8,29,16,tzinfo=timezone.utc)
    from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
    db_session.add(TeamSchedule(team_name='Texas',season=2026,week=2,location='bye',is_bye=True))
    score(db_session,p,opener,{'rush_yards':50}); score(db_session,p,later,{'rush_yards':900})
    db_session.commit()
    row=client.get('/player-rankings',params={'period':'season'}).json()['data'][0]
    assert row['fantasy_points']==5 and row['games']==1


def test_league_scores_full_pool_before_filtering_own_players_and_checks_membership(client, db_session):
    uid,headers=identity(client)
    outsider,other_headers=identity(client,'outsider')
    league=League(name='Custom ranks',season_year=2026,commissioner_user_id=uid)
    db_session.add(league);db_session.flush()
    rules=get_scoring_rules(); rules['offense']['receptions']=0
    db_session.add(LeagueSettings(league_id=league.id,conference_codes=['SEC'],scoring_json=rules))
    db_session.add(LeagueMember(league_id=league.id,user_id=uid))
    team=Team(league_id=league.id,name='Mine',owner_user_id=uid);db_session.add(team);db_session.flush()
    g=game(db_session)
    mine=player(db_session,'Owned WR','WR'); rival=player(db_session,'Other WR','WR')
    score(db_session,mine,g,{'receptions':10,'rec_yards':10});score(db_session,rival,g,{'receptions':0,'rec_yards':100})
    outside=player(db_session,'Other conference','WR','Miami'); cg=game(db_session,school='Miami');score(db_session,outside,cg,{'rec_yards':500})
    db_session.add(RosterEntry(league_id=league.id,team_id=team.id,player_id=mine.id,slot='WR',status='starter'))
    db_session.commit()
    global_rows=client.get('/player-rankings',params={'position':'WR'}).json()['data']
    assert next(r for r in global_rows if r['id']==mine.id)['fantasy_points']==11
    result=client.get('/player-rankings',params={'league_id':league.id,'mine':True},headers=headers)
    assert result.status_code==200,result.text
    data=result.json()['data']; assert len(data)==1 and data[0]['id']==mine.id
    assert data[0]['fantasy_points']==1 and data[0]['position_rank']==2
    assert client.get('/player-rankings',params={'league_id':league.id},headers=other_headers).status_code==403
    assert client.get('/player-rankings',params={'league_id':league.id}).status_code==401
    assert client.get('/player-rankings',params={'mine':True},headers=headers).status_code==422


def test_last_regular_season_week_becomes_available_after_its_rollover(monkeypatch):
    monkeypatch.setattr(player_rankings,"calendar_cfb_week",lambda season:15)
    assert player_rankings.completed_through_week(2026,datetime(2026,12,15,12,59,tzinfo=timezone.utc))==14
    assert player_rankings.completed_through_week(2026,datetime(2026,12,15,13,0,tzinfo=timezone.utc))==15


def test_default_never_hides_missing_latest_week_by_falling_back_to_older_results(client,db_session):
    p=player(db_session,'Previous leader');g=game(db_session,week=1);score(db_session,p,g,{'rush_yards':100});db_session.commit()
    latest=client.get('/player-rankings/leaders').json()
    assert latest['week']==2 and all(x['player'] is None for x in latest['data'])
    row=client.get('/player-rankings',params={'period':'season'}).json()['data'][0]
    assert row['status']=='pending' and row['fantasy_points'] is None and row['missing_games']==1
    prior=client.get('/player-rankings',params={'week':1}).json()['data'][0]
    assert prior['fantasy_points']==10 and prior['position_rank']==1
