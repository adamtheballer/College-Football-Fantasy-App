"""Read-only, full-catalog ESPN identity and game-history audit; never writes a database."""
import argparse
import asyncio,json,re,pathlib,sys,time
from datetime import datetime,timezone
from types import SimpleNamespace
import httpx
from collegefootballfantasy_api.app.services.espn_player_lookup import _item_name_matches,_school_matches,_position_matches
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--inventory',type=pathlib.Path,required=True);parser.add_argument('--cache-dir',type=pathlib.Path,required=True);parser.add_argument('--season',type=int,action='append',required=True);parser.add_argument('--requests-per-second',type=float,default=2);parser.add_argument('--retry-unmatched',action='store_true');parser.add_argument('--max-cache-age-hours',type=float,default=24)
args=parser.parse_args()
if args.max_cache_age_hours<0:raise SystemExit('Cache age must be nonnegative')
if not 0<args.requests_per_second<=4:raise SystemExit('Requests per second must be positive and at most 4')
root=args.cache_dir;root.mkdir(parents=True,exist_ok=True)
players=json.loads(args.inventory.read_text())
if len({p['id'] for p in players})!=len(players):raise SystemExit('Catalog contains duplicate internal player IDs')
base='https://site.web.api.espn.com/apis/common/v3/sports/football/college-football/athletes/'
lock=asyncio.Lock();next_request=0;sem=asyncio.Semaphore(4);done=0
async def fetch(client,url,path,params=None):
 global next_request
 if path.exists() and time.time()-path.stat().st_mtime < args.max_cache_age_hours*3600:return json.loads(path.read_text())
 for attempt in range(3):
  async with lock:
   delay=max(0,next_request-time.monotonic());await asyncio.sleep(delay);next_request=time.monotonic()+1/args.requests_per_second
  try:
   r=await client.get(url,params=params);r.raise_for_status();payload=r.json()
   if not isinstance(payload,dict):raise ValueError('Expected JSON object')
   path.write_text(json.dumps(payload));return payload
  except (httpx.HTTPError,ValueError):
   if attempt==2:raise
   await asyncio.sleep(min(2**attempt,4))
async def audit(client,p):
 global done
 row={'id':p['id'],'name':p['name'],'school':p['school'],'position':p['position'],'seasons':{}}
 async with sem:
  candidate=re.search(r'/players/full/(\d+)\.png',p.get('image_url') or '')
  if not candidate:row['identity_status']='no_candidate'
  else:
   pid=candidate[1];row['candidate_provider_id']=pid
   try:
    profile=await fetch(client,base+pid,root/f'profile-{pid}.json');athlete=profile.get('athlete',{});player=SimpleNamespace(**p)
    if str(athlete.get('id'))!=pid or not (_item_name_matches(athlete,player) and _school_matches(profile,player) and _position_matches(profile,player)):
     row['identity_status']='mismatch';row['source_name']=athlete.get('displayName');row['source_school']=(athlete.get('team')or{}).get('shortDisplayName');row['source_position']=(athlete.get('position')or{}).get('abbreviation')
    else:
     row['identity_status']='verified_profile'
     for season in sorted(set(args.season)):
      try:
       payload=await fetch(client,base+pid+'/gamelog',root/f'gamelog-{pid}-{season}.json',{'season':season})
       selected=next((f.get('value') for f in payload.get('filters',[]) if f.get('name')=='season'),None)
       events=[e for st in payload.get('seasonTypes',[]) for c in st.get('categories',[]) for e in c.get('events',[])]
       row['seasons'][str(season)]={'status':'available' if str(selected)==str(season) and events else 'no_stats' if str(selected)==str(season) else 'wrong_season','games':len({str(e.get('eventId')) for e in events}),'source_season':selected}
      except Exception as exc:row['seasons'][str(season)]={'status':'fetch_failed','error':type(exc).__name__}
   except Exception as exc:row['identity_status']='fetch_failed';row['error']=type(exc).__name__
  if args.retry_unmatched and row['identity_status'] in {'no_candidate','mismatch'}:
   try:
    query=await fetch(client,'https://site.web.api.espn.com/apis/common/v3/search',root/f'search-{p["id"]}.json',{'query':p['name'],'type':'player','limit':10,'region':'us','lang':'en','contentorigin':'espn'})
    candidates=list(query.get('items',[])) + [item for group in query.get('results',[]) for item in group.get('contents',[])]
    # ESPN also uses a flat results list on some search responses.
    candidates += [item for item in query.get('results',[]) if isinstance(item,dict) and item.get('id')]
    matched=[];player=SimpleNamespace(**p)
    for candidate in candidates:
     if not _item_name_matches(candidate,player) or str(candidate.get('sport') or '').lower()!='football' or str(candidate.get('league') or '').lower()!='college-football':continue
     pid=str(candidate.get('id') or '')
     if not pid.isdecimal():continue
     profile=await fetch(client,base+pid,root/f'profile-{pid}.json');athlete=profile.get('athlete',{})
     if str(athlete.get('id'))==pid and _item_name_matches(athlete,player) and _school_matches(profile,player) and _position_matches(profile,player):matched.append(pid)
    matched=list(dict.fromkeys(matched))
    if len(matched)==1:
     pid=matched[0];row['candidate_provider_id']=pid;row['identity_status']='verified_profile'
     for season in sorted(set(args.season)):
      payload=await fetch(client,base+pid+'/gamelog',root/f'gamelog-{pid}-{season}.json',{'season':season})
      selected=next((f.get('value') for f in payload.get('filters',[]) if f.get('name')=='season'),None)
      events=[e for st in payload.get('seasonTypes',[]) for c in st.get('categories',[]) for e in c.get('events',[])]
      row['seasons'][str(season)]={'status':'available' if str(selected)==str(season) and events else 'no_stats' if str(selected)==str(season) else 'wrong_season','games':len({str(e.get('eventId')) for e in events}),'source_season':selected}
    elif len(matched)>1:row['identity_status']='ambiguous_search'
   except Exception as exc:row['lookup_error']=type(exc).__name__
  if row['identity_status']=='verified_profile' and p['position']=='K':
   from collegefootballfantasy_api.app.services.player_game_history import parse_game_history,parse_boxscore_game_history,game_history_fallback_team_ids,completed_schedule_event_ids
   for year,source in row['seasons'].items():
    if source['status'] not in {'available','no_stats'}:continue
    try:
     payload=json.loads((root/f'gamelog-{row["candidate_provider_id"]}-{year}.json').read_text())
     if parse_game_history(payload,season=int(year)):continue
     fallback=[]
     event_ids=set(payload.get('events',{}))
     profile=json.loads((root/f'profile-{row["candidate_provider_id"]}.json').read_text())
     team_ids=game_history_fallback_team_ids(payload,season=int(year),profile=profile)
     for team_id in team_ids:
      schedule=await fetch(client,f'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/{team_id}/schedule',root/f'schedule-{team_id}-{year}.json',{'dates':int(year)})
      if str(schedule.get('season',{}).get('year'))!=year:raise ValueError('Team schedule season mismatch')
      event_ids.update(completed_schedule_event_ids(schedule.get('events',[]),team_id=team_id))
     source['fallback_team_ids']=team_ids
     for event_id in sorted(event_ids):
      summary=await fetch(client,'https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary',root/f'summary-{event_id}.json',{'event':event_id})
      fact=parse_boxscore_game_history(summary,provider_player_id=row['candidate_provider_id'],season=int(year))
      if fact:fallback.append(event_id)
     source['boxscore_events']=fallback
     if fallback:source['status']='available';source['games']=len(fallback)
    except Exception as exc:source['status']='fetch_failed';source['error']=type(exc).__name__
  done+=1
  (root/f'audit-{p["id"]}.json').write_text(json.dumps(row))
  if done%50==0:print(f'Audited {done}/{len(players)} public player identities and season game logs',flush=True)
  return row
async def main():
 async with httpx.AsyncClient(timeout=25,follow_redirects=True) as client:rows=await asyncio.gather(*(audit(client,p) for p in players))
 ids={}
 for row in rows:
  if row['identity_status']=='verified_profile':ids.setdefault(row['candidate_provider_id'],[]).append(row)
 for group in ids.values():
  if len(group)>1:
   for row in group:row['identity_status']='ambiguous_catalog_id'
 report={'captured_at':datetime.now(timezone.utc).isoformat(),'catalog_size':len(players),'public_source_only':True,'production_writes':0,'players':rows}
 (root/'audit.json').write_text(json.dumps(report,indent=2));print('Complete public stats audit:',len(rows),flush=True)
asyncio.run(main())
