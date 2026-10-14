"""Audit or replay a complete public catalog cache into an explicit local DB.

Release hold: this script cannot write to a production database. The existing
historical importer is the post-authorization operator entry point.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.historical_stats import HistoricalStatImportRun
from collegefootballfantasy_api.app.services.player_game_history import store_player_game_history,parse_game_history,store_boxscore_game_history,parse_boxscore_game_history
from collegefootballfantasy_api.app.services.espn_player_lookup import _item_name_matches,_school_matches,_position_matches
from collegefootballfantasy_api.app.services.provider_identity import upsert_player_provider_mapping

def import_cache(db, *, audit: dict, cache_dir: Path, apply: bool) -> dict:
    entries=audit['players']
    if audit['catalog_size']!=len(entries) or len({r['id'] for r in entries})!=len(entries):
        raise ValueError('A complete, unique catalog audit is required')
    coverage=[];run=None
    if apply:
        run=HistoricalStatImportRun(provider='espn',requested_player_ids=[r['id'] for r in entries],requested_seasons=sorted({int(season) for entry in entries for season in entry['seasons']}),status='running',started_at=datetime.now(timezone.utc),players_requested=len(entries),trigger_type='local_verified_cache')
        db.add(run);db.commit()
    for entry in entries:
        outcome={'player_id':entry['id'],'identity_status':entry['identity_status'],'seasons':[]}
        try:
            with db.begin_nested():
                player=db.get(Player,entry['id'])
                if player is None or (player.name,player.school,player.position)!=(entry['name'],entry['school'],entry['position']):
                    raise ValueError('Catalog player identity changed or is absent')
                if entry['identity_status']!='verified_profile':
                    outcome['status']='unmatched'
                else:
                    provider_id=entry['candidate_provider_id']
                    profile=json.loads((cache_dir/f'profile-{provider_id}.json').read_text());athlete=profile.get('athlete',{})
                    if str(athlete.get('id'))!=provider_id or not (_item_name_matches(athlete,player) and _school_matches(profile,player) and _position_matches(profile,player)):
                        raise ValueError('Cached profile does not verify current player identity')
                    if apply:
                        upsert_player_provider_mapping(db,player_id=player.id,provider='espn',provider_player_id=provider_id,provider_team_id=str((athlete.get('team')or{}).get('id')),verification_status='verified',match_confidence=1,reason='Public profile identity verified by exact checks or source-reviewed, ID-scoped name/role exceptions; current school verified independently.')
                        db.flush()
                    for season_text,source in entry['seasons'].items():
                        season=int(season_text)
                        if source['status'] not in {'available','no_stats'}:
                            raise ValueError(f'Unusable provider response for season {season}: {source["status"]}')
                        payload=json.loads((cache_dir/f'gamelog-{provider_id}-{season}.json').read_text())
                        facts=parse_game_history(payload,season=season)
                        if apply:
                            result=store_player_game_history(db,player,provider_player_id=provider_id,season=season,payload=payload)
                        else:result={'season':season,'games':len(facts),'status':'available' if facts else 'no_stats'}
                        for event_id in source.get('boxscore_events',[]):
                            summary=json.loads((cache_dir/f'summary-{event_id}.json').read_text())
                            if apply:boxed=store_boxscore_game_history(db,player,provider_player_id=provider_id,season=season,summary=summary)
                            else:
                                fact=parse_boxscore_game_history(summary,provider_player_id=provider_id,season=season)
                                boxed={'games':1 if fact else 0,'status':'available' if fact else 'no_stats'}
                            result['games']+=boxed['games']
                            for counter in ('inserted','updated','unchanged'):
                                if counter in result:result[counter]+=boxed[counter]
                            if result['games']:result['status']='available'
                        outcome['seasons'].append(result)
                    outcome['status']='available' if any(r['games'] for r in outcome['seasons']) else 'no_stats'
            if apply:db.commit()
        except Exception as exc:
            outcome['status']='failed';outcome['error']=type(exc).__name__+': '+str(exc)
            if apply:db.rollback()
        coverage.append(outcome)
        if apply:
            run=db.get(HistoricalStatImportRun,run.id)
            counts=Counter(r['status'] for r in coverage)
            run.players_succeeded=counts['available'];run.players_not_found=counts['no_stats'];run.players_unmatched=counts['unmatched'];run.players_failed=counts['failed']
            run.error_summary={'coverage':coverage,'counts':dict(counts)};db.commit()
    counts=Counter(r['status'] for r in coverage)
    report={'requested':len(entries),'counts':dict(counts),'games':sum(s['games'] for r in coverage if r['status']=='available' for s in r['seasons']),'apply_local':apply,'production_writes':0,'coverage':coverage}
    if apply:
        run=db.get(HistoricalStatImportRun,run.id);run.status='completed_with_errors' if counts['failed'] or counts['unmatched'] else 'completed';run.completed_at=datetime.now(timezone.utc);db.commit();report['run_id']=run.id
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url',required=True);parser.add_argument('--cache-dir',type=Path,required=True);parser.add_argument('--apply-local',action='store_true')
    args=parser.parse_args();url=make_url(args.database_url)
    if args.apply_local and url.host not in {'localhost','127.0.0.1','::1'}:
        raise SystemExit('Release hold: local database writes only')
    ensure_models_registered()
    with Session(create_engine(url)) as db:
        report=import_cache(db,audit=json.loads((args.cache_dir/'audit.json').read_text()),cache_dir=args.cache_dir,apply=args.apply_local)
        if not args.apply_local:db.rollback()
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
