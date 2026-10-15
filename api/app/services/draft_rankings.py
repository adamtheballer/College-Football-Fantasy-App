"""One authoritative implementation of the existing positional-value draft model.

Ported from the established React policy. Weights/position rules/editorial moves
are preserved; invalid ranks are bucketed last and forecasts are never altered.
"""
from __future__ import annotations
import math
import hashlib
import re
import unicodedata
from functools import lru_cache
from statistics import mean, stdev
from pathlib import Path
from collegefootballfantasy_api.app.services import cfb27_player_sync

POLICY_VERSION = "positional-value-master-v2-valid-ranks"
POSITIONS = ("QB", "RB", "WR", "TE", "K")
DEFAULT_SLOTS = {"QB":1,"RB":2,"WR":2,"TE":1,"K":1,"BE":6,"IR":0}

def number(value):
    if isinstance(value,bool) or value is None or value == "":
        return None
    try:
        result=float(value)
        return result if math.isfinite(result) else None
    except (ValueError,TypeError):
        return None

def rank(value):
    result=number(value)
    return result if result is not None and result>0 else None

def source_rank(player):
    return next((valid for key in ("boardRank","adp","rank") if (valid:=rank(player.get(key))) is not None),None)

def forecast(player):
    for key in ("restOfSeasonProjectedPoints","sheetProjectedSeasonPoints"):
        value=number(player.get(key))
        if value is not None and value>=0:
            return value
    value=number((player.get("sheetProjectionStats") or {}).get("fpts"))
    return value if value is not None and value>=0 else None

def clamp(value,low,high):
    return max(low,min(high,value))

def z(value,values):
    return (value-mean(values))/(stdev(values) or 1) if len(values)>1 else 0

def percentile(value,values):
    if not values or max(values)==min(values):
        return .5
    return clamp((value-min(values))/(max(values)-min(values)),0,1)

def rank_percentile(value,total):
    return .5 if value is None or total<=1 else clamp(1-(value-1)/(total-1),0,1)

def identity(value):
    value=''.join(c for c in unicodedata.normalize('NFKD',str(value or '')) if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]+',' ',value).strip()

def rating_key(value):
    value=re.sub(r'\b(jr\.?|iii|ii|iv)\b','',str(value).lower().replace('&','and'))
    return re.sub(r'[^a-z0-9]+','',value)

@lru_cache(maxsize=1)
def _rating_lookup(source_path, source_revision):
    rows=cfb27_player_sync.load_cfb27_ratings_from_snapshot(Path(source_path))
    exact={(rating_key(row.name),rating_key(row.school),row.position):row for row in rows}
    by_name={}
    ranges={pos:[row.overall for row in rows if row.position==pos] for pos in POSITIONS}
    for row in rows:
        by_name.setdefault((rating_key(row.name),row.position),[]).append(row)
    return exact,by_name,ranges

def talent(player, source_revision):
    exact,by_name,ranges=_rating_lookup(str(cfb27_player_sync.CFB27_SOURCE_PATH.resolve()), source_revision)
    key=(rating_key(player.get('name')),rating_key(player.get('school')),player['pos'])
    rating=exact.get(key)
    matches=by_name.get((key[0],key[2]),[])
    if rating is None and len(matches)==1:
        rating=matches[0]
    return (rating.overall,percentile(rating.overall,ranges[rating.position])) if rating else (None,.5)

def build_master_draft_board(players: list[dict], config: dict) -> list[dict]:
    size=int(config.get('leagueSize',12));slots={**DEFAULT_SLOTS,**config.get('rosterSlots',{})}
    eligible={int(p['id']):{**p,'id':int(p['id'])} for p in players if p.get('pos') in POSITIONS and rank(p.get('id')) is not None and float(p['id']).is_integer()}
    entries=[]
    for player in sorted(eligible.values(),key=lambda p:p['id']):
        points=forecast(player)
        # Missing forecasts remain distinguishable from real zero. Neutral
        # model input is never emitted as a claimed projection.
        entries.append({'player':player,'projectedPoints':points if points is not None else 0,'projectionMissing':points is None,'historyPoints':number(((player.get('history') or [{}])[0].get('stats') or {}).get('fpts')) or 0})
    if not entries:
        return []
    ratings_revision=hashlib.sha256(cfb27_player_sync.CFB27_SOURCE_PATH.read_bytes()).hexdigest()
    projections=[e['projectedPoints'] for e in entries]
    by_pos={pos:[e['projectedPoints'] for e in entries if e['player']['pos']==pos] for pos in POSITIONS}
    history={pos:[e['historyPoints'] for e in entries if e['player']['pos']==pos] for pos in POSITIONS}
    bench={'QB':.1,'RB':.35,'WR':.35,'TE':.1,'K':.05}
    replacements={}
    for pos,values in by_pos.items():
        if values:
            # Match JS Math.round for nonnegative roster demand.
            index=max(1,math.floor(slots[pos]*size+(slots['BE']+slots['IR'])*size*bench[pos]+.5))-1
            replacements[pos]=sorted(values,reverse=True)[min(index,len(values)-1)]
    max_plays=max(1,*[number((e['player'].get('projection') or {}).get('expectedPlays')) or 0 for e in entries])
    max_spread=max(1,*[max(1,(number((e['player'].get('projection') or {}).get('ceiling')) or 0)-(number((e['player'].get('projection') or {}).get('floor')) or 0)) for e in entries])
    scarcity=[e['projectedPoints']-replacements.get(e['player']['pos'],0) for e in entries]
    for e,scarce in zip(entries,scarcity):
        p=e['player'];pos=p['pos'];projection=p.get('projection') or {}
        e['scarcity']=scarce
        role=clamp(1-((rank(p.get('posRank')) or 20)-1)/30,.4,.95)
        penalty=(.05 if p.get('status') in {'OUT','QUESTIONABLE','DOUBTFUL','IR'} else 0)+((1-role)*.05 if pos in {'RB','WR','TE'} else 0)
        floor=number(projection.get('floor'));ceiling=number(projection.get('ceiling'))
        spread=max(1,(ceiling if ceiling is not None else e['projectedPoints']*1.3)-(floor if floor is not None else e['projectedPoints']*.7))
        environment=clamp((number(projection.get('expectedPlays')) or 0)/max_plays,.4,1.1)
        consistency=clamp(1-spread/max_spread,.2,.9)
        tpr=(.55*z(e['projectedPoints'],projections)+.15*z(scarce,scarcity)+.1*role+.1*z(e['historyPoints'],history[pos])+.05*environment+.05*consistency-penalty)*{'QB':.89,'RB':1.05,'WR':1.08,'TE':.92,'K':.65}[pos]
        ovr,talent_score=talent(p, ratings_revision)
        e.update(roleCertainty=role,penalty=penalty,tprScore=tpr,cfb27Overall=ovr,cfb27TalentScore=talent_score,sourceBoardRank=source_rank(p))
    computed={e['player']['id']:index+1 for index,e in enumerate(sorted(entries,key=lambda e:(-e['tprScore'],e['player']['id'])))}
    qb_replacement=replacements.get('QB',0)
    def low_qb(e):
        return e['player']['pos']=='QB' and e['projectedPoints']<max(60,qb_replacement*.4)
    for e in entries:
        p=e['player'];provided=e['sourceBoardRank'];cr=computed[p['id']]
        aware=provided
        if p['pos']=='QB' and not low_qb(e) and provided is not None and provided-cr>=24 and e['projectedPoints']>=max(180,qb_replacement*.85):
            aware=min(provided,cr+12)
        fantasy=.65*percentile(e['scarcity'],scarcity)+.35*percentile(e['projectedPoints'],projections)
        market=.6*rank_percentile(cr,len(entries))+.4*rank_percentile(aware,len(entries))
        e['finalDraftScore']=.6*fantasy+.2*market+.12*e['cfb27TalentScore']+.08*e['roleCertainty']-e['penalty']
    board=sorted(entries,key=lambda e:(low_qb(e),-e['projectedPoints'] if low_qb(e) else 0,-e['finalDraftScore'],computed[e['player']['id']],e['player']['id']))
    shallow=[e for e in board if not low_qb(e)];deep=[e for e in board if low_qb(e)]
    rounds=config.get('totalRosterSpots') or sum(slots.values())
    kicker_floor=max(100,size*rounds-size*2)
    adjusted=[(max(index+1,kicker_floor) if e['player']['pos']=='K' else index+1+{'QB':28,'WR':-3,'TE':24}.get(e['player']['pos'],0),index,e) for index,e in enumerate(shallow)]
    board=[e for _,_,e in sorted(adjusted,key=lambda t:t[:2])]+sorted(deep,key=lambda e:(-e['projectedPoints'],e['sourceBoardRank'] or math.inf,e['player']['id']))
    if slots['QB']==1:
        early_size=min(len(board),size*6);limit=size+max(2,math.ceil(size*.15))
        accepted=[];deferred=[];count=0
        for e in board[:early_size]:
            if e['player']['pos']=='QB' and count>=limit:
                deferred.append(e)
            else:
                accepted.append(e);count+=e['player']['pos']=='QB'
        later=board[early_size:];promoted=[e for e in later if e['player']['pos']!='QB'][:len(deferred)]
        promoted_ids={e['player']['id'] for e in promoted}
        board=accepted+promoted+deferred+[e for e in later if e['player']['id'] not in promoted_ids]
    for pos in POSITIONS:
        indexes=[i for i,e in enumerate(board) if e['player']['pos']==pos]
        ordered=sorted((board[i] for i in indexes),key=lambda e:(-e['projectedPoints'],board.index(e)))
        for index,e in zip(indexes,ordered):
            board[index]=e
    protected=sorted((e for e in board if e['player'].get('restOfSeasonAsOfWeek')==1 and e['player'].get('status')=='HEALTHY' and e['sourceBoardRank'] is not None and e['sourceBoardRank']<=6),key=lambda e:e['sourceBoardRank'])
    for e in protected:
        old=board.index(e);new=min(len(board)-1,int(e['sourceBoardRank'])-1+3)
        if old>new:
            board.pop(old);board.insert(new,e)
    for name,target in [('kj duff',10),('nick marsh',11)]:
        e=next((e for e in board if e['player']['pos']=='WR' and identity(e['player'].get('name'))==name),None)
        if e:
            old=board.index(e);minimum=max([0]+[i+1 for i,candidate in enumerate(board) if candidate['player']['pos']=='WR' and candidate['projectedPoints']>e['projectedPoints']])
            new=max(min(target-1,len(board)-1),minimum)
            board.pop(old);board.insert(new,e)
    # Apply the required validity contract after every preserved model rule.
    # A positional/ROS-only rank cannot make an unranked source a top draft pick.
    ranked=[e for e in board if e['sourceBoardRank'] is not None]
    unranked=sorted((e for e in board if e['sourceBoardRank'] is None),key=lambda e:(e['projectionMissing'],-e['projectedPoints'],identity(e['player'].get('name')),e['player']['id']))
    board=ranked+unranked
    tier=1;start=0;result=[]
    for index,e in enumerate(board):
        if index and index-start>=4 and board[index-1]['projectedPoints']>0 and (board[index-1]['projectedPoints']-e['projectedPoints'])/board[index-1]['projectedPoints']>=.12:
            tier+=1;start=index
        result.append({**e['player'],'masterDraftRank':index+1,'draftRank':index+1,'sourceBoardRank':e['sourceBoardRank'],'projectedPoints':None if e['projectionMissing'] else e['projectedPoints'],'projectionMissing':e['projectionMissing'],'tier':tier,'tprScore':e['tprScore'],'finalDraftScore':round(e['finalDraftScore'],4),'cfb27Overall':e['cfb27Overall'],'cfb27TalentScore':round(e['cfb27TalentScore'],4)})
    return result


@lru_cache(maxsize=16)
def _cached_board(serialized_inputs: str, serialized_config: str, source_revision: str):
    # Only pure values are cached. Each request fingerprints every authoritative
    # input and the ratings file; no ORM rows, league availability or old DB
    # context can survive a source change.
    import json
    return build_master_draft_board(json.loads(serialized_inputs), json.loads(serialized_config))


def build_draft_ranking_snapshot(db, *, season: int, league_id: int | None = None, config: dict | None = None) -> dict:
    """Rank the full context before search, drafted-player filters or pagination."""
    import hashlib
    import json
    from sqlalchemy import select
    from collegefootballfantasy_api.app.models.player import Player
    from collegefootballfantasy_api.app.models.league import League
    from collegefootballfantasy_api.app.models.league_settings import LeagueSettings
    from collegefootballfantasy_api.app.crud.projection import current_published_projections_query
    from collegefootballfantasy_api.app.services.player_pool_filters import canonical_fantasy_player_filter, season_eligible_player_filter, league_conference_player_filter
    from collegefootballfantasy_api.app.services.draft_board_outlook import build_rest_of_season_draft_board
    from collegefootballfantasy_api.app.services.injury_status import reviewed_injuries_for_week, normalize_injury_status
    from collegefootballfantasy_api.app.services.league_weeks import calendar_cfb_week
    from collegefootballfantasy_api.app.services.player_chart_publication import points_from_verified_stats
    config=config or {'leagueSize':12,'totalRosterSpots':13,'rosterSlots':DEFAULT_SLOTS}
    conference_codes=None;scoring_rules=None
    if league_id is not None:
        league=db.get(League,league_id)
        if league is None:
            raise ValueError('league not found')
        season=league.season_year
        settings=db.query(LeagueSettings).filter_by(league_id=league_id).one_or_none()
        if settings:
            from collegefootballfantasy_api.app.services.league_flow import FIXED_ROSTER_SLOTS
            raw=settings.roster_slots_json or FIXED_ROSTER_SLOTS
            config={'leagueSize':league.max_teams,'totalRosterSpots':sum(raw.get(key,0) for key in ('QB','RB','WR','TE','K','FLEX','SUPERFLEX','BENCH')),'rosterSlots':{**{key:raw.get(key,0) for key in ('QB','RB','WR','TE','K')},'BE':raw.get('BENCH',0)+raw.get('FLEX',0)+raw.get('SUPERFLEX',0),'IR':0}}
            conference_codes=settings.conference_codes
            scoring_rules=settings.scoring_json or None
    players=db.scalars(select(Player).where(canonical_fantasy_player_filter(season),season_eligible_player_filter(season),league_conference_player_filter(conference_codes)).order_by(Player.id)).all()
    outlook=build_rest_of_season_draft_board(db,season=season,scoring_rules=scoring_rules)
    week=calendar_cfb_week(season)
    projections={row.player_id:row for row in db.scalars(current_published_projections_query(season=season,week=week,player_ids=tuple(p.id for p in players))).all()}
    injuries=reviewed_injuries_for_week(db,season=season,week=week,player_ids={p.id for p in players})
    rows=[]
    for p in players:
        projection=projections.get(p.id);future=outlook.get(p.id)
        season_points = points_from_verified_stats(p.sheet_projection_stats or {},position=p.position,rules=scoring_rules) if scoring_rules else p.sheet_projected_season_points
        source=p.sheet_adp if rank(p.sheet_adp) is not None else p.cfb27_rank
        # The source rank is distinct from the raw ROS projection-total rank.
        rows.append({'id':p.id,'name':p.name,'school':p.school,'pos':p.position,'boardRank':None,'adp':p.sheet_adp,'rank':source,'posRank':p.cfb27_position_rank,'status':('HEALTHY' if normalize_injury_status(injuries[p.id].status)=='FULL' else normalize_injury_status(injuries[p.id].status)) if p.id in injuries else 'UNREPORTED','sheetProjectedSeasonPoints':season_points,'sheetProjectionStats':{**(p.sheet_projection_stats or {}),'fpts':season_points},'restOfSeasonProjectedPoints':future.projected_points if future else None,'restOfSeasonRank':future.rank if future else None,'restOfSeasonAsOfWeek':future.completed_week if future else None,'restOfSeasonUpdatedAt':future.updated_at if future and future.updated_at else None,'history':[],'projection':{'floor':projection.floor if projection else 0,'ceiling':projection.ceiling if projection else 0,'expectedPlays':projection.expected_plays if projection else 0}})
    payload={'policy':POLICY_VERSION,'season':season,'week':week,'config':config,'scoring_rules':scoring_rules,'ratings_source':str(cfb27_player_sync.CFB27_SOURCE_PATH),'ratings_hash':hashlib.sha256(cfb27_player_sync.CFB27_SOURCE_PATH.read_bytes()).hexdigest(),'inputs':rows}
    serialized_inputs=json.dumps(rows,sort_keys=True,default=str)
    version=hashlib.sha256(json.dumps(payload,sort_keys=True,default=str).encode()).hexdigest()
    from copy import deepcopy
    board=deepcopy(_cached_board(serialized_inputs,json.dumps(config,sort_keys=True),payload['ratings_hash']))
    dates={row['id']:row['restOfSeasonUpdatedAt'] for row in rows}
    for row in board:
        row['restOfSeasonUpdatedAt']=dates[row['id']]
    return {'season':season,'week':week,'config':config,'version':version,'policy':POLICY_VERSION,'board':{r['id']:r for r in board},'players':{p.id:p for p in players}}
