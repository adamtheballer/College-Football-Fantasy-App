from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import pytest
from sqlalchemy.exc import IntegrityError
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_historical_game_stat import PlayerHistoricalGameStat
from collegefootballfantasy_api.app.models.player_stat import PlayerStat
from collegefootballfantasy_api.app.models.team_schedule import TeamSchedule
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.services.player_game_history import parse_game_history,store_player_game_history,GameHistoryParseError

FIXTURE=Path(__file__).parents[1]/'fixtures/espn-alex-perry-game-history-2025.json'
def fixture():return json.loads(FIXTURE.read_text())
def player(db):
    p=Player(name='Alex Perry',school='Illinois',position='WR',external_id='espn:5084133');db.add(p);db.flush();return p

def test_source_verified_transfer_history_full_regular_and_bowl_without_live_score_writes(client,db_session):
    p=player(db_session)
    result=store_player_game_history(db_session,p,provider_player_id='5084133',season=2025,payload=fixture())
    db_session.add(TeamSchedule(team_name='Illinois',season=2026,week=1,opponent_name='Duke',location='home',is_bye=False,neutral_site=False,conference_game=False,date_confirmed=False))
    db_session.commit()
    assert result['games']==13
    body=client.get(f'/players/{p.id}/game-log',params={'season':2025}).json()
    assert body['available_seasons']==[2026,2025]
    assert body['team_name']=='FIU'
    summary={stat['label']:stat['value'] for stat in body['season_summary']['stats']}
    assert summary['Receptions']==56 and summary['Rec Yds']==840 and summary['Rec TD']==9
    rows={row['provider_event_id']:row for row in body['games']}
    assert len(rows)==13
    stats=rows['401757311']['stats']
    assert stats['stats']['receptions']==7 and stats['stats']['rec_yards']==140 and stats['stats']['rec_tds']==2
    assert rows['401757311']['result']=='W 56–16'
    assert stats['fantasy_points']==33
    assert rows['401778315']['season_type']=='postseason' and rows['401778315']['stats']['stats']['rec_yards']==24
    expected={'Middle Tennessee':(5,71,2),'Liberty':(8,88,1),'Jacksonville State':(4,109,1),'Sam Houston':(7,140,2),'UTSA':(3,24,0)}
    for opponent,values in expected.items():
        game=next(row for row in body['games'] if opponent in row['opponent_name'])
        assert tuple(game['stats']['stats'][field] for field in ('receptions','rec_yards','rec_tds'))==values
    assert all(row["date"].startswith("2025-") for row in body["games"])

    assert db_session.query(PlayerStat).count()==0
    default=client.get(f'/players/{p.id}/game-log').json()
    assert default['season']==2025 and len(default['games'])==13
    current=client.get(f'/players/{p.id}/game-log',params={'season':2026}).json()
    assert len(current['games'])==1 and current['games'][0]['stats'] is None
    assert store_player_game_history(db_session,p,provider_player_id='5084133',season=2025,payload=fixture())['unchanged']==13


def test_schema_season_identity_malformed_and_future_rejection(db_session):
    p=player(db_session)
    with pytest.raises(ValueError,match='trusted'):store_player_game_history(db_session,p,provider_player_id='999',season=2025,payload=fixture())
    with pytest.raises(GameHistoryParseError,match='different season'):parse_game_history(fixture(),season=2026)
    broken=fixture();broken['seasonTypes'][0]['categories'][0]['events'][0]['stats'].pop()
    with pytest.raises(GameHistoryParseError,match='column count'):parse_game_history(broken,season=2025)
    future=fixture()
    assert parse_game_history(future,season=2025,now=datetime(2025,1,1,tzinfo=timezone.utc))==[]
    unknown=fixture();unknown['names']=['unknown_'+str(i) for i in range(len(unknown['names']))]
    with pytest.raises(GameHistoryParseError,match='recognized'):parse_game_history(unknown,season=2025)


def test_source_correction_updates_exact_game_keeps_zero_and_same_week_bowl_separate(db_session):
    p=player(db_session);payload=fixture()
    store_player_game_history(db_session,p,provider_player_id='5084133',season=2025,payload=payload)
    payload['seasonTypes'][0]['categories'][0]['events'][0]['stats'][1]='0'
    result=store_player_game_history(db_session,p,provider_player_id='5084133',season=2025,payload=payload)
    assert result['updated']==13 and db_session.query(PlayerHistoricalGameStat).count()==13
    assert db_session.query(PlayerHistoricalGameStat).filter_by(provider_event_id='401778315').one().stats['rec_yards']==0
    assert db_session.query(PlayerHistoricalGameStat).filter_by(week=1).count()==2
    db_session.commit()


def test_existing_schedule_row_merges_same_event_without_duplicate_or_moving_transfer_team(client,db_session):
    p=player(db_session);store_player_game_history(db_session,p,provider_player_id='5084133',season=2025,payload=fixture())
    g=Game(external_id='401757311',season=2025,week=14,home_team='Sam Houston',away_team='FIU',home_points=16,away_points=56,neutral_site=False)
    db_session.add(g);db_session.flush()
    db_session.add(TeamSchedule(team_name='FIU',season=2025,week=14,game_id=g.id,opponent_name='Sam Houston',location='away',is_bye=False,neutral_site=False,conference_game=False,date_confirmed=True))
    db_session.commit()
    body=client.get(f'/players/{p.id}/game-log',params={'season':2025}).json()
    assert len(body['games'])==13
    # History supplies the represented team even without imported season totals.
    assert body['team_name']=='FIU'


def test_finite_fields_and_result_crosscheck():
    payload=fixture();payload['events']['401757311']['gameResult']='L'
    with pytest.raises(GameHistoryParseError,match='disagrees'):parse_game_history(payload,season=2025)
    payload=fixture();payload['seasonTypes'][1]['categories'][0]['events'][0]['stats'][1]='NaN'
    with pytest.raises(GameHistoryParseError,match='numeric'):parse_game_history(payload,season=2025)


def test_provider_filters_only_means_unavailable_production_without_fabricated_zero():
    payload={'filters':[{'name':'season','value':'2026','options':[{'value':'2025'}]}]}
    assert parse_game_history(payload,season=2026)==[]
    payload['names']=[]
    with pytest.raises(GameHistoryParseError,match='Missing named'):parse_game_history(payload,season=2026)


def test_game_history_derived_totals_are_read_only_and_official_season_rows_win(db_session,monkeypatch):
    from collegefootballfantasy_api.app.core.config import settings
    from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
    from collegefootballfantasy_api.app.services.historical_stats import get_player_historical_stats_response,canonical_historical_season_rows
    monkeypatch.setattr(settings,'player_card_historical_stats_enabled',True)
    p=player(db_session);store_player_game_history(db_session,p,provider_player_id='5084133',season=2025,payload=fixture());db_session.commit()
    history=get_player_historical_stats_response(db_session,p,season=2025)
    assert history.status=='available'
    assert history.seasons[0].games_played is None  # a stat log cannot certify total participation
    assert history.seasons[0].freshness.is_final is False
    receiving=next(row for row in history.seasons[0].categories if row.key=='receiving')
    assert {row.label:row.value for row in receiving.stats}['Receptions']==56
    assert db_session.query(PlayerHistoricalSeasonStat).count()==0
    db_session.add(PlayerHistoricalSeasonStat(player_id=p.id,provider='google_season_stats',provider_player_id='official',season=2025,season_type='regular',team_name='FIU',receptions=57,parser_version='verified',imported_at=datetime.now(timezone.utc),is_final=True));db_session.flush()
    rows=canonical_historical_season_rows(db_session,player_id=p.id,season=2025)
    assert len(rows)==1 and rows[0].receptions==57


def test_dual_role_kicker_boxscore_fallback_requires_exact_athlete_final_and_season(client,db_session):
    from collegefootballfantasy_api.app.services.player_game_history import parse_boxscore_game_history,store_boxscore_game_history
    summary=json.loads((FIXTURE.parent/'espn-ryon-sayeri-final-boxscore-2025.json').read_text())
    fact=parse_boxscore_game_history(summary,provider_player_id='5221037',season=2025)
    assert fact['stats']['field_goals_made']==4 and fact['stats']['extra_points_made']==1
    assert fact['stats']['espn_field_goal_distance_detail_available'] is True
    assert parse_boxscore_game_history(summary,provider_player_id='999999',season=2025) is None
    live=deepcopy(summary);live['header']['competitions'][0]['status']['type']['completed']=False
    assert parse_boxscore_game_history(live,provider_player_id='5221037',season=2025) is None
    assert parse_boxscore_game_history(summary,provider_player_id='5221037',season=2025,now=datetime(2025,1,1,tzinfo=timezone.utc)) is None
    with pytest.raises(GameHistoryParseError,match='season mismatch'):parse_boxscore_game_history(summary,provider_player_id='5221037',season=2026)
    p=Player(name='Ryon Sayeri',school='USC',position='K',external_id='espn:5221037');db_session.add(p);db_session.commit()
    assert store_boxscore_game_history(db_session,p,provider_player_id='5221037',season=2025,summary=summary)['inserted']==1
    db_session.commit()
    body=client.get(f'/players/{p.id}/game-log',params={'season':2025}).json();game=body['games'][0]
    assert game['stats']['source']=='espn_boxscore_history' and game['stats']['fantasy_points'] is not None
    assert '/summary?event=401778327' in game['source_url']
    assert store_boxscore_game_history(db_session,p,provider_player_id='5221037',season=2025,summary=summary)['unchanged']==1
    assert db_session.query(PlayerStat).count()==0


def test_boxscore_unknown_counts_never_become_zero():
    from collegefootballfantasy_api.app.services.player_game_history import parse_boxscore_game_history
    summary=json.loads((FIXTURE.parent/'espn-ryon-sayeri-final-boxscore-2025.json').read_text())
    category=summary['boxscore']['players'][0]['statistics'][0]
    category['athletes'][0]['stats'][category['keys'].index('fieldGoalsMade/fieldGoalAttempts')]='--'
    with pytest.raises(GameHistoryParseError,match='Unknown made'):parse_boxscore_game_history(summary,provider_player_id='5221037',season=2025)


def test_kicking_fallback_uses_historical_teams_and_only_completed_schedule_events():
    from collegefootballfantasy_api.app.services.player_game_history import game_history_fallback_team_ids,completed_schedule_event_ids
    payload={'events':{'1':{'team':{'id':'30'}}}}
    profile={'athlete':{'team':{'id':'2116'}}}
    assert game_history_fallback_team_ids(payload,season=2025,profile=profile)==['30']
    year=datetime.now(timezone.utc).year
    assert set(game_history_fallback_team_ids(payload,season=year,profile=profile))=={'30','2116'}
    good={'id':'100','date':'2025-01-01T00:00:00Z','competitions':[{'status':{'type':{'completed':True}},'competitors':[{'id':'30'},{'id':'1'}]}]}
    future={**good,'id':'101','date':'2100-01-01T00:00:00Z'}
    live=deepcopy(good);live['id']='102';live['competitions'][0]['status']['type']['completed']=False
    assert completed_schedule_event_ids([good,future,live],team_id='30')=={'100'}
    assert completed_schedule_event_ids([good],team_id='999')==set()

@pytest.mark.parametrize('counts,expected_season', [(None, 2025), ({'receptions': 0, 'rec_yards': 0, 'rec_tds': 0}, 2026)])
def test_default_history_ignores_metadata_placeholder_but_preserves_recorded_zero(client, db_session, counts, expected_season):
    from collegefootballfantasy_api.app.models.player_game_stat import PlayerGameStat
    p = player(db_session)
    store_player_game_history(db_session, p, provider_player_id='5084133', season=2025, payload=fixture())
    game = Game(external_id='401858424', season=2026, week=1, home_team='Illinois', away_team='UAB', home_points=42, away_points=23, neutral_site=False)
    db_session.add(game)
    db_session.flush()
    db_session.add(TeamSchedule(team_name='Illinois', season=2026, week=1, game_id=game.id, opponent_name='UAB', location='home', is_bye=False, neutral_site=False, conference_game=False, date_confirmed=True))
    stored = PlayerGameStat(player_id=p.id, game_id=game.id, season=2026, week=1, source='espn_final_boxscore', stats={'backfill_zero_stat': True, 'EventID': game.external_id, **(counts or {})})
    db_session.add(stored)
    db_session.commit()
    body = client.get(f'/players/{p.id}/game-log').json()
    assert body['season'] == expected_season
    assert len(body['games']) == (13 if expected_season == 2025 else 1)
    current = client.get(f'/players/{p.id}/game-log?season=2026').json()
    if counts is None:
        assert current['games'][0]['stats'] is None
        assert current['games'][0]['stat_status'] == 'missing'
    else:
        assert current['games'][0]['stats']['fantasy_points'] == 0
    # Retrieval must never rewrite the legacy source or live league scores.
    db_session.refresh(stored)
    assert stored.stats == {'backfill_zero_stat': True, 'EventID': game.external_id, **(counts or {})}
