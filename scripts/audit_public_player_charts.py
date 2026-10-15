"""Read-only full-inventory chart audit; never publishes or authenticates."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json
from pathlib import Path
import time
import httpx


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--inventory',type=Path,required=True)
    parser.add_argument('--season',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    players=json.loads(args.inventory.read_text())
    if len({p['id'] for p in players})!=len(players):
        raise SystemExit('Inventory contains duplicate stable player IDs')
    started=datetime.now(timezone.utc).isoformat()
    with httpx.Client(base_url=args.base_url.rstrip('/')+'/',timeout=30) as client:
        def fetch(player):
            error=None
            for attempt in range(3):
                try:
                    response=client.get(f"players/{player['id']}/trajectory",params={'season':args.season})
                    response.raise_for_status()
                    body=response.json()
                    if body['player_id']!=player['id'] or body['season']!=args.season:
                        raise ValueError('Chart context mismatch')
                    projection,value=body['projection'],body['value']
                    if any(len({p['week'] for p in series})!=len(series) for series in [projection,value]):
                        raise ValueError('Duplicate chart weeks')
                    actual=[p['week'] for p in projection if p.get('actual_points') is not None]
                    forecasts=[p['week'] for p in projection if p.get('points') is not None and p.get('actual_points') is None and not p.get('is_finalized',False)]
                    return {'player_id':player['id'],'name':player['name'],'position':player['position'],'school':player['school'],'projection_weeks':[p['week'] for p in projection],'actual_weeks':actual,'forecast_weeks':forecasts,'bye_weeks':[p['week'] for p in projection if p['source']=='bye'],'finality_field_present':all('is_finalized' in p for p in projection),'value_points':value}
                except (httpx.HTTPError,ValueError,KeyError) as exc:
                    error=str(exc)
                    if attempt<2: time.sleep(attempt+1)
            return {'player_id':player['id'],'name':player['name'],'error':error}
        results=[]
        with ThreadPoolExecutor(max_workers=4) as executor:
            pending={executor.submit(fetch,p):p['id'] for p in players}
            for i,future in enumerate(as_completed(pending),start=1):
                results.append(future.result())
                if i%100==0: print(f'Audited {i}/{len(players)} public charts',flush=True)
    results.sort(key=lambda row:row['player_id'])
    valid=[row for row in results if 'error' not in row]
    report={'started_at':started,'completed_at':datetime.now(timezone.utc).isoformat(),'base_url':args.base_url,'season':args.season,'mode':'public-read-only','inventory_count':len(players),'successes':len(valid),'errors':len(results)-len(valid),'players_with_actual_points':sum(bool(r['actual_weeks']) for r in valid),'players_with_multiple_unfinished_forecasts':sum(len(r['forecast_weeks'])>1 for r in valid),'players_without_explicit_finality':sum(not r['finality_field_present'] for r in valid),'weekly_value_snapshots':sum(sum(p['week']>0 for p in r['value_points']) for r in valid),'by_week':{str(w):{'actual_players':sum(w in r['actual_weeks'] for r in valid),'forecast_players':sum(w in r['forecast_weeks'] for r in valid),'value_players':sum(any(p['week']==w for p in r['value_points']) for r in valid)} for w in range(1,14)},'limitations':['Public API replies do not prove source-stat completeness or authoritative matchup finality.','Flat values are not classified as errors without the historical formula inputs.','No database access, authentication, migrations or repair writes were performed.'],'players':results}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:value for key,value in report.items() if key not in {'players','by_week'}}))


if __name__=='__main__': main()
