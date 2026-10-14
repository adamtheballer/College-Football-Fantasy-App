"""Strict, season-keyed ESPN per-game history for the complete player catalog.

This read model does not certify fantasy weeks or alter live league scores.
Unknown stats and unmatched identities never become zero production.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import re
from sqlalchemy.orm import Session
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.player_historical_game_stat import PlayerHistoricalGameStat
from collegefootballfantasy_api.app.services.historical_stats import canonical_json_hash, resolve_espn_player_id
from collegefootballfantasy_api.app.domain.stat_normalization import strip_unscored_return_stats
from collegefootballfantasy_api.app.schemas.game_log import PlayerGameLogRowRead, PlayerGameLogStatRead
from collegefootballfantasy_api.app.services.player_chart_publication import points_from_verified_stats

PARSER_VERSION = 'espn_game_history_v1'
# ESPN's named columns are authoritative; positional guesses are forbidden.
FIELDS = {
    'completions':'passing_completions','passingAttempts':'passing_attempts',
    'passingYards':'pass_yards','passingTouchdowns':'pass_tds','interceptions':'interceptions',
    'rushingAttempts':'rushing_attempts','rushingYards':'rush_yards','rushingTouchdowns':'rush_tds','longRushing':'long_rush',
    'receptions':'receptions','receivingTargets':'receiving_targets','receivingYards':'rec_yards',
    'receivingTouchdowns':'rec_tds','longReception':'long_reception',
    'fumbles':'fumbles','fumblesLost':'fumbles_lost',
    'fieldGoals':'field_goals_made','fieldGoalsMade':'field_goals_made','fieldGoalsAttempted':'field_goals_attempted','totalKickingPoints':'kick_points',
    'extraPointsMade':'extra_points_made','extraPointsAttempted':'extra_points_attempted',
    'fieldGoalsMissed':'fg_missed',
}

class GameHistoryParseError(ValueError):
    pass

def _number(value):
    if value is None or isinstance(value,bool) or str(value).strip() in {'','-','--','—','N/A'}:
        return None
    try:
        result=float(str(value).replace(',',''))
        return result if math.isfinite(result) else None
    except (ValueError,TypeError):
        return None

def parse_game_history(payload: dict, *, season: int, now: datetime | None = None) -> list[dict]:
    if not isinstance(payload,dict):
        raise GameHistoryParseError('Expected ESPN game-log object')
    selected=next((f.get('value') for f in payload.get('filters',[]) if isinstance(f,dict) and f.get('name')=='season'),None)
    if str(selected)!=str(season):
        raise GameHistoryParseError('Provider returned a different season')
    # ESPN's explicit no-production response contains season filters only.
    # Distinguish this supported empty shape from a broken partial schema.
    if set(payload)=={'filters'}:
        return []
    names=payload.get('names');events=payload.get('events');season_types=payload.get('seasonTypes')
    if not isinstance(names,list) or not isinstance(events,dict) or not isinstance(season_types,list):
        raise GameHistoryParseError('Missing named game-log columns, events or season types')
    if len(names)!=len(set(names)):
        raise GameHistoryParseError('Duplicate named stat columns')
    now=now or datetime.now(timezone.utc)
    output={}
    for split in season_types:
        for category in split.get('categories',[]):
            season_type={'2':'regular','3':'postseason'}.get(str(category.get('splitType')))
            if season_type is None:
                if category.get('events'): raise GameHistoryParseError('Unknown season type')
                continue
            for item in category.get('events',[]):
                event_id=str(item.get('eventId') or '')
                event=events.get(event_id)
                values=item.get('stats')
                if not event_id.isdecimal() or not isinstance(event,dict) or str(event.get('id'))!=event_id or not isinstance(values,list) or len(values)!=len(names):
                    raise GameHistoryParseError('Unlinked game or stat column count mismatch')
                try:
                    kickoff=datetime.fromisoformat(str(event['gameDate']).replace('Z','+00:00'))
                    week=int(event['week'])
                except (KeyError,TypeError,ValueError) as exc:
                    raise GameHistoryParseError('Missing verified game date/week') from exc
                if kickoff.tzinfo is None or week<0:
                    raise GameHistoryParseError('Invalid game date/week')
                # Stats alone do not prove a final. Require dated result and
                # both scores; never import a future/scheduled/live event.
                result=event.get('gameResult')
                home_score=_number(event.get('homeTeamScore'));away_score=_number(event.get('awayTeamScore'))
                if kickoff>now or result not in {'W','L','T'} or home_score is None or away_score is None:
                    continue
                team=event.get('team') or {};opponent=event.get('opponent') or {}
                team_id=str(team.get('id') or '')
                if team_id not in {str(event.get('homeTeamId')),str(event.get('awayTeamId'))} or not team_id.isdecimal():
                    raise GameHistoryParseError('Game does not identify the represented team')
                opponent_id=str(opponent.get('id') or '')
                if opponent_id==team_id or opponent_id not in {str(event.get('homeTeamId')),str(event.get('awayTeamId'))}:
                    raise GameHistoryParseError('Game opponent identity mismatch')
                team_name=team.get('shortDisplayName') or team.get('displayName') or team.get('abbreviation')
                opponent_name=opponent.get('shortDisplayName') or opponent.get('displayName') or opponent.get('abbreviation')
                if not team_name or not opponent_name:
                    raise GameHistoryParseError('Missing historical team or opponent')
                stats={}
                for name,value in zip(names,values):
                    field=FIELDS.get(name)
                    parsed=_number(value)
                    if field and parsed is not None:stats[field]=parsed
                    elif field and str(value).strip() not in {'','-','--','—','N/A'}:
                        raise GameHistoryParseError('Invalid numeric production')
                    elif field in {'pass_yards','pass_tds','interceptions','rush_yards','rush_tds','rec_yards','rec_tds','receptions','fumbles_lost','extra_points_made'}:
                        stats['_scoring_incomplete']=True
                    if name in {'fieldGoalsMade/fieldGoalAttempts','fieldGoalsMade-fieldGoalAttempts','extraPointsMade/extraPointAttempts','extraPointsMade-extraPointAttempts','extraPoints'} and re.fullmatch(r'\d+[-/]\d+',str(value)):
                        made,attempted=map(int,re.split(r'[-/]',str(value)))
                        if made>attempted: raise GameHistoryParseError('Invalid made/attempted counts')
                        prefix='field_goals' if name.startswith('field') else 'extra_points'
                        stats[f'{prefix}_made']=made;stats[f'{prefix}_attempted']=attempted
                if not stats:
                    raise GameHistoryParseError('No recognized numeric production for game row')
                own,opp=(home_score,away_score) if team_id==str(event.get('homeTeamId')) else (away_score,home_score)
                expected='W' if own>opp else 'L' if own<opp else 'T'
                if result!=expected: raise GameHistoryParseError('Result disagrees with game scores')
                row={'provider_event_id':event_id,'season':season,'season_type':season_type,'week':week,'provider_team_id':team_id,'team_name':team_name,'opponent_name':opponent_name,'kickoff_at':kickoff,'location':'away' if event.get('atVs')=='@' else 'neutral' if event.get('neutralSite') or team_id!=str(event.get('homeTeamId')) else 'home','result':f'{result} {int(own)}–{int(opp)}','stats':strip_unscored_return_stats(stats)}
                if event_id in output and output[event_id]!=row:
                    raise GameHistoryParseError('Conflicting duplicate game rows')
                output[event_id]=row
    return sorted(output.values(),key=lambda row:(row['kickoff_at'],row['provider_event_id']))

def store_player_game_history(db: Session, player: Player, *, provider_player_id: str, season: int, payload: dict) -> dict:
    if resolve_espn_player_id(db,player)!=str(provider_player_id):
        raise ValueError('Game history requires the current trusted player identity')
    parsed=parse_game_history(payload,season=season)
    return _store_game_facts(db,player,provider_player_id=provider_player_id,season=season,payload=payload,facts=parsed)


def _store_game_facts(db,player,*,provider_player_id,season,payload,facts,source_url=None):
    parsed=facts
    digest=canonical_json_hash(payload);now=datetime.now(timezone.utc)
    coverage={'player_id':player.id,'season':season,'games':len(parsed),'inserted':0,'updated':0,'unchanged':0,'status':'available' if parsed else 'no_stats'}
    for fact in parsed:
        row=db.query(PlayerHistoricalGameStat).filter_by(player_id=player.id,season=season,provider='espn',provider_event_id=fact['provider_event_id']).with_for_update().one_or_none()
        if row and row.source_response_hash==digest:
            coverage['unchanged']+=1;continue
        if row is None:
            row=PlayerHistoricalGameStat(player_id=player.id,provider='espn',provider_player_id=str(provider_player_id),position=player.position)
            db.add(row);coverage['inserted']+=1
        else:coverage['updated']+=1
        # Keep the historical scoring position after a later position change.
        for key,value in fact.items():setattr(row,key,value)
        row.source_response_hash=digest;row.imported_at=now
        row.source_url=source_url or f'https://www.espn.com/college-football/player/gamelog/_/id/{provider_player_id}/type/college-football/year/{season}'
    db.flush()
    return coverage

def historical_game_read(row: PlayerHistoricalGameStat, *, scoring_rules: dict | None) -> PlayerGameLogRowRead:
    stats=dict(row.stats)
    if stats.get('_scoring_incomplete') or (row.position=='K' and stats.get('field_goals_made',0)>0 and not stats.get('espn_field_goal_distance_detail_available')):
        # Per-game totals do not establish exact field-goal distance tiers.
        points=None
    else:
        if row.position=='K' and 'extra_points_made' in stats:stats['xp_made']=stats['extra_points_made']
        points=points_from_verified_stats(stats,position=row.position,rules=scoring_rules)
    return PlayerGameLogRowRead(schedule_id=None,provider_event_id=row.provider_event_id,season_type=row.season_type,source_url=row.source_url,team_name=row.team_name,week=row.week,date=row.kickoff_at.date(),kickoff_at=row.kickoff_at,opponent_name=row.opponent_name,location=row.location,location_label=row.location.title(),neutral_site=row.location=='neutral',conference_game=False,game_status='final',stat_status='final',result=row.result,stats=PlayerGameLogStatRead(source='espn_boxscore_history' if '/summary?' in row.source_url else 'espn_athlete_gamelog',stats=stats,fantasy_points=points,updated_at=row.imported_at))


def derived_historical_season_rows(db: Session, *, player_id: int, season: int | None = None):
    """Expose totals of verified game records only when season imports are absent.

    These transient read models are never written as an official season total,
    and never sum ESPN's overlapping regular/postseason summary totals.
    """
    from collections import defaultdict
    from collegefootballfantasy_api.app.models.historical_stats import PlayerHistoricalSeasonStat
    query=db.query(PlayerHistoricalGameStat).filter_by(player_id=player_id)
    if season is not None:query=query.filter_by(season=season)
    groups=defaultdict(list)
    for game in query.order_by(PlayerHistoricalGameStat.kickoff_at).all():
        groups[(game.season,game.provider_team_id)].append(game)
    rows=[]
    field_map={**{value:value for value in FIELDS.values()},'pass_yards':'passing_yards','pass_tds':'passing_touchdowns','rush_yards':'rushing_yards','rush_tds':'rushing_touchdowns','rec_yards':'receiving_yards','rec_tds':'receiving_touchdowns'}
    for (year,team_id),games in groups.items():
        first=games[0]
        row=PlayerHistoricalSeasonStat(player_id=player_id,provider='espn_athlete_gamelog',provider_player_id=first.provider_player_id,provider_team_id=team_id,season=year,season_type='verified_games',team_name=first.team_name,position=first.position,games_played=None,parser_version=PARSER_VERSION,imported_at=max(game.imported_at for game in games),source_response_hash=first.source_response_hash,source_url=first.source_url,is_final=False,scoring_rules_version='default')
        for key,field in field_map.items():
            if not hasattr(PlayerHistoricalSeasonStat,field):continue
            values=[game.stats[key] for game in games if isinstance(game.stats.get(key),(int,float))]
            if values:setattr(row,field,max(values) if field in {'long_rush','long_reception'} else sum(values))
        points=[historical_game_read(game,scoring_rules=None).stats.fantasy_points for game in games]
        if all(value is not None for value in points):
            row.fantasy_points=round(sum(points),2)
        rows.append(row)
    return rows


def parse_boxscore_game_history(summary: dict, *, provider_player_id: str, season: int, now=None):
    """Recover named production from a final game when athlete logs omit a role.

    Reuses the existing box-score stat and field-goal distance parser. It never
    turns a missing athlete into a zero/DNP or publishes live fantasy scores.
    """
    from collegefootballfantasy_api.app.integrations.espn import extract_player_box_score_stats,ESPN_STAT_KEY_MAP
    header=summary.get('header') or {}
    if header.get('season',{}).get('year')!=season:raise GameHistoryParseError('Box score season mismatch')
    event_id=str(header.get('id') or '')
    if not event_id.isdecimal():raise GameHistoryParseError('Box score event identity missing')
    competitions=header.get('competitions') or []
    if len(competitions)!=1:raise GameHistoryParseError('Ambiguous box score game')
    game=competitions[0]
    if str(game.get('id'))!=event_id:raise GameHistoryParseError('Box score game identity mismatch')
    if game.get('status',{}).get('type',{}).get('completed') is not True:return None
    try:kickoff=datetime.fromisoformat(game['date'].replace('Z','+00:00'))
    except (KeyError,ValueError,TypeError) as exc:raise GameHistoryParseError('Missing box score date') from exc
    if kickoff.tzinfo is None:raise GameHistoryParseError('Undated box score')
    if kickoff>(now or datetime.now(timezone.utc)):return None
    represented_team=None
    for team in summary.get('boxscore',{}).get('players',[]):
        for category in team.get('statistics',[]):
            keys=category.get('keys') or []
            for athlete in category.get('athletes',[]):
                if str(athlete.get('athlete',{}).get('id'))!=str(provider_player_id):continue
                if represented_team is not None and represented_team!=str(team['team']['id']):raise GameHistoryParseError('Athlete on conflicting teams')
                represented_team=str(team['team']['id'])
                values=athlete.get('stats')
                if not isinstance(values,list) or len(values)!=len(keys):raise GameHistoryParseError('Box score stat column mismatch')
                for key,value in zip(keys,values):
                    if key in {'completions/passingAttempts','extraPointsMade/extraPointAttempts','fieldGoalsMade/fieldGoalAttempts'}:
                        if not re.fullmatch(r'\d+[/\-]\d+',str(value)):raise GameHistoryParseError('Unknown made/attempted production')
                        made,attempted=map(int,re.split(r'[/\-]',str(value)))
                        if made>attempted:raise GameHistoryParseError('Invalid made/attempted production')
                    elif key in ESPN_STAT_KEY_MAP and _number(value) is None:
                        raise GameHistoryParseError('Unknown numeric box score production')
    if represented_team is None:return None
    rows=[row for row in extract_player_box_score_stats(summary) if row['ESPNPlayerID']==str(provider_player_id)]
    if len(rows)!=1:return None
    allowed=set(FIELDS.values())|{'xp_made','fg_missed','field_goals_made','field_goals_attempted','extra_points_made','extra_points_attempted','fg_made_0_30','fg_made_31_40','fg_made_41_50','fg_made_51_60','fg_made_61_plus','espn_field_goal_distance_detail_available'}
    stats={key:value for key,value in rows[0].items() if key in allowed}
    if not any(isinstance(value,(int,float)) and not isinstance(value,bool) for value in stats.values()):return None
    teams=game.get('competitors') or []
    if len(teams)!=2 or len({str(t.get('id')) for t in teams})!=2:raise GameHistoryParseError('Box score competitor mismatch')
    own=next((team for team in teams if str(team.get('id'))==represented_team),None)
    other=next((team for team in teams if str(team.get('id'))!=represented_team),None)
    if not own or not other:raise GameHistoryParseError('Box score represented team missing')
    a=_number(own.get('score'));b=_number(other.get('score'))
    if a is None or b is None or min(a,b)<0 or not a.is_integer() or not b.is_integer():raise GameHistoryParseError('Box score final score missing')
    week=header.get('week');kind={2:'regular',3:'postseason'}.get(header.get('season',{}).get('type'))
    if type(week) is not int or week<0 or kind is None:raise GameHistoryParseError('Box score season type/week missing')
    location='neutral' if game.get('neutralSite') else own.get('homeAway')
    if location not in {'home','away','neutral'}:raise GameHistoryParseError('Box score location missing')
    return {'provider_event_id':event_id,'season':season,'season_type':kind,'week':week,'provider_team_id':represented_team,'team_name':own['team'].get('shortDisplayName') or own['team']['displayName'],'opponent_name':other['team'].get('shortDisplayName') or other['team']['displayName'],'kickoff_at':kickoff,'location':location,'result':f"{'W' if a>b else 'L' if a<b else 'T'} {int(a)}–{int(b)}",'stats':strip_unscored_return_stats(stats)}


def store_boxscore_game_history(db,player,*,provider_player_id,season,summary):
    if resolve_espn_player_id(db,player)!=str(provider_player_id):raise ValueError('Box score history requires the current trusted player identity')
    fact=parse_boxscore_game_history(summary,provider_player_id=provider_player_id,season=season)
    return _store_game_facts(db,player,provider_player_id=provider_player_id,season=season,payload=summary,facts=[fact] if fact else [],source_url=f"https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={summary.get('header',{}).get('id')}")


def game_history_fallback_team_ids(payload,*,season,profile=None):
    """Use represented historical teams; current profile only for current year."""
    teams={str(event.get('team',{}).get('id')) for event in payload.get('events',{}).values() if str(event.get('team',{}).get('id') or '').isdecimal()}
    if season==datetime.now(timezone.utc).year and profile:
        team=str(profile.get('athlete',{}).get('team',{}).get('id') or '')
        if team.isdecimal():teams.add(team)
    return sorted(teams)


def completed_schedule_event_ids(events,*,team_id):
    ids=set()
    for event in events:
        competitions=event.get('competitions') or []
        if len(competitions)!=1:continue
        game=competitions[0]
        if game.get('status',{}).get('type',{}).get('completed') is not True:continue
        if not any(str(team.get('id'))==str(team_id) for team in game.get('competitors',[])):continue
        try:date=datetime.fromisoformat(event['date'].replace('Z','+00:00'))
        except (KeyError,TypeError,ValueError):continue
        if date.tzinfo is None or date>datetime.now(timezone.utc):continue
        event_id=str(event.get('id') or '')
        if event_id.isdecimal():ids.add(event_id)
    return ids
