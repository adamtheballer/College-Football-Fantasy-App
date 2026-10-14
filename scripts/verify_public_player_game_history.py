"""Read-only whole-catalog public API parity against a verified local ESPN cache."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlparse
import httpx
from collegefootballfantasy_api.app.services.player_game_history import parse_game_history,parse_boxscore_game_history

async def verify(base_url, audit, cache):
    if urlparse(base_url).hostname not in {'localhost','127.0.0.1','::1'}:
        raise ValueError('This verification harness requires an isolated localhost API')
    entries=audit['players']
    if len(entries)!=audit['catalog_size'] or len({p['id'] for p in entries})!=len(entries):
        raise ValueError('A full unique catalog audit is required')
    gate=asyncio.Semaphore(4);done=0
    async with httpx.AsyncClient(base_url=base_url,timeout=45) as client:
        async def one(entry):
            nonlocal done
            row={'player_id':entry['id'],'name':entry['name'],'position':entry['position'],'identity_status':entry['identity_status'],'seasons':[]}
            async with gate:
                try:
                    if not entry['seasons']:
                        reply=await client.get(f'/players/{entry["id"]}/game-log')
                        reply.raise_for_status()
                        if reply.json()['player_id']!=entry['id']:raise ValueError('API player mismatch')
                    for year,source in entry['seasons'].items():
                        reply=await client.get(f'/players/{entry["id"]}/game-log',params={'season':year})
                        reply.raise_for_status();body=reply.json()
                        if body['player_id']!=entry['id'] or body['season']!=int(year):raise ValueError('API player/season mismatch')
                        payload=json.loads((cache/f'gamelog-{entry["candidate_provider_id"]}-{year}.json').read_text())
                        facts=parse_game_history(payload,season=int(year))
                        for event_id in source.get('boxscore_events',[]):
                            summary=json.loads((cache/f'summary-{event_id}.json').read_text())
                            fact=parse_boxscore_game_history(summary,provider_player_id=entry['candidate_provider_id'],season=int(year))
                            if fact:facts.append(fact)
                        returned={game.get('provider_event_id'):game for game in body['games'] if game.get('provider_event_id')}
                        if len(returned)!=sum(bool(game.get('provider_event_id')) for game in body['games']):raise ValueError('Duplicate API provider events')
                        for fact in facts:
                            game=returned.get(fact['provider_event_id'])
                            if not game or not game.get('stats'):raise ValueError('Source-verified game/stat is absent from API')
                            if game['team_name']!=fact['team_name'] or game['result']!=fact['result']:raise ValueError('Historical team/result mismatch')
                            if game['stats']['source'] in {'espn_athlete_gamelog','espn_boxscore_history'}:
                                if any(game['stats']['stats'].get(k)!=v for k,v in fact['stats'].items()):raise ValueError('Source/API stat mismatch')
                        row['seasons'].append({'season':int(year),'source_games':len(facts),'matched_games':len(facts),'status':'available' if facts else 'no_stats'})
                    row['status']='verified' if entry['identity_status']=='verified_profile' else 'unmatched'
                except Exception as exc:
                    row['status']='failed';row['error']=type(exc).__name__+': '+str(exc)
                done+=1
                if done%100==0:print(f'Checked API stats for {done}/{len(entries)} players',flush=True)
                return row
        rows=await asyncio.gather(*(one(entry) for entry in entries))
    return {'verified_at':datetime.now(timezone.utc).isoformat(),'base_url':base_url,'players_reviewed':len(rows),'counts':dict(Counter(row['status'] for row in rows)),'source_game_records_checked':sum(s['matched_games'] for row in rows for s in row['seasons']),'production_writes':0,'coverage':rows}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True);parser.add_argument('--cache-dir',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=asyncio.run(verify(args.base_url,json.loads((args.cache_dir/'audit.json').read_text()),args.cache_dir))
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print({key:value for key,value in report.items() if key!='coverage'})
    return 1 if report['counts'].get('failed') else 0

if __name__=='__main__':raise SystemExit(main())
