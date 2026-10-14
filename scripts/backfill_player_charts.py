"""Audit finalized chart coverage; apply only to an explicitly supplied local DB.

Production operation is intentionally read-only during the combined release hold.
"""
from __future__ import annotations
import argparse
import json
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.models.player_chart_week import PlayerChartWeek
from collegefootballfantasy_api.app.models.player_trade_value import PlayerTradeValue
from collegefootballfantasy_api.app.services.fantasy_week_finality import week_is_authoritatively_finalized,latest_known_finalized_week
from collegefootballfantasy_api.app.services.player_chart_publication import eligible_chart_players_query, publish_finalized_chart_week,verified_fantasy_week_stats,points_from_verified_stats
from collegefootballfantasy_api.app.services.player_trade_value import calculate_weekly_trade_values,value_cutoff_context

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url',required=True)
    parser.add_argument('--season',type=int,required=True)
    parser.add_argument('--weeks',type=int,nargs='+',default=list(range(1,14)))
    parser.add_argument('--apply-local',action='store_true')
    args=parser.parse_args()
    target=make_url(args.database_url)
    if args.apply_local and not (target.drivername.startswith('sqlite') or target.host in {'localhost','127.0.0.1','::1'}):
        raise SystemExit('Release hold: writes are permitted only to an explicitly supplied local database')
    if any(not 1 <= week <=13 for week in args.weeks):
        raise SystemExit('Fantasy weeks must be 1–13')
    ensure_models_registered()
    with Session(create_engine(target,pool_pre_ping=True)) as db:
        players=eligible_chart_players_query(db,args.season).order_by('id').all()
        player_ids=[p.id for p in players]
        report={'season':args.season,'eligible':len(player_ids),'apply_local':args.apply_local,'weeks':[]}
        latest_finalized=latest_known_finalized_week(db,season=args.season)
        for week in sorted(set(args.weeks)):
            finalized=week_is_authoritatively_finalized(db,season=args.season,week=week)
            entry={'week':week,'finalized':finalized,'actual_snapshots_before':db.query(PlayerChartWeek).filter(PlayerChartWeek.player_id.in_(player_ids),PlayerChartWeek.season==args.season,PlayerChartWeek.week==week).count(),'value_snapshots_before':db.query(PlayerTradeValue).filter(PlayerTradeValue.player_id.in_(player_ids),PlayerTradeValue.season==args.season,PlayerTradeValue.week==week).count()}
            if finalized:
                facts=verified_fantasy_week_stats(db,season=args.season,week=week,players=players)
                actuals={r.player_id:r for r in db.query(PlayerChartWeek).filter_by(season=args.season,week=week).all()}
                values={r.player_id:r for r in db.query(PlayerTradeValue).filter_by(season=args.season,week=week,policy_version="universal_v2").all()}
                supported={p.id for p in players if p.id in facts and points_from_verified_stats(facts[p.id].stats,position=(actuals[p.id].stats_json.get("_chart_position",p.position) if p.id in actuals else p.position)) is not None}
                entry.update({"supported_source_actuals":len(supported),"missing_source_ids":sorted(set(player_ids)-supported),"missing_actual_ids":sorted(set(player_ids)-set(actuals)),"missing_value_ids":sorted(set(player_ids)-set(values)),"unrecoverable_value_input_ids":sorted(p.id for p in players if week<latest_finalized and not value_cutoff_context(values.get(p.id))),"original_forecast_unavailable_ids":sorted(pid for pid,row in actuals.items() if pid in player_ids and not row.stats_json.get("_chart_forecast"))})
            if args.apply_local and finalized:
                entry['actual_publication']=publish_finalized_chart_week(db,season=args.season,week=week)
                entry['value_publication']=calculate_weekly_trade_values(db,season=args.season,week=week)
            entry['actual_snapshots_after']=db.query(PlayerChartWeek).filter(PlayerChartWeek.player_id.in_(player_ids),PlayerChartWeek.season==args.season,PlayerChartWeek.week==week).count()
            entry['value_snapshots_after']=db.query(PlayerTradeValue).filter(PlayerTradeValue.player_id.in_(player_ids),PlayerTradeValue.season==args.season,PlayerTradeValue.week==week).count()
            report['weeks'].append(entry)
        if args.apply_local:
            db.commit()
        print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
