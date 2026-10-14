"""Certify chart migration against disposable local PostgreSQL only."""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from scripts.certify_postseason_migrations import _require_disposable_postgres, _run_alembic, _temporary_database

PREVIOUS = '0118_native_push_delivery'
HEAD = '0119_player_chart_history'

def main():
    raw=os.environ.get('CHART_TEST_DATABASE_URL')
    if not raw:
        raise SystemExit('Set CHART_TEST_DATABASE_URL to a disposable localhost PostgreSQL DB')
    base=make_url(raw); _require_disposable_postgres(base)
    if base.host not in {'localhost','127.0.0.1','::1'} or not (base.database or '').startswith('cff_push_'):
        raise SystemExit('Requires localhost and cff_push_* database')
    with _temporary_database(base) as url:
        _run_alembic(url,'upgrade',PREVIOUS)
        engine=create_engine(url)
        try:
            with engine.begin() as db:
                player=db.scalar(text("INSERT INTO players (name, position, school) VALUES ('Chart Migration','WR','Texas') RETURNING id"))
                db.execute(text("INSERT INTO player_trade_values (player_id, season, week, value, tier, confidence, policy_version, calculated_at, input_version) VALUES (:player,2026,1,75,'GOOD_BENCH_OPTION',1,'universal_v2',now(),'preserved')"),{'player':player})
            _run_alembic(url,'upgrade',HEAD)
            with engine.connect() as db:
                assert db.scalar(text('SELECT value FROM player_trade_values')) == 75
                assert db.scalar(text('SELECT input_context_json FROM player_trade_values')) is None
                assert db.scalar(text('SELECT count(*) FROM player_chart_weeks')) == 0
            _run_alembic(url,'downgrade',PREVIOUS)
            _run_alembic(url,'upgrade',HEAD)
            with engine.begin() as db:
                db.execute(text("INSERT INTO player_chart_weeks (player_id,season,week,stats_json,standard_points,scoring_rules_json,input_hash,finalized_at,calculation_version) VALUES (:player,2026,1,'{}',0,'{}',:hash,now(),'test')"),{'player':player,'hash':'a'*64})
            try:
                _run_alembic(url,'downgrade',PREVIOUS)
            except RuntimeError as exc:
                assert 'retaining history' in str(exc)
            else:
                raise AssertionError('Published history must prevent destructive downgrade')
            _run_alembic(url,'upgrade','head')
            with engine.connect() as db:
                assert db.scalar(text('SELECT count(*) FROM player_chart_forecasts')) == 0
            _run_alembic(url,'downgrade','0120_player_game_history')
            _run_alembic(url,'upgrade','head')
            with engine.begin() as db:
                db.execute(text("INSERT INTO player_chart_forecasts (player_id,season,week,snapshot_json,captured_at) VALUES (:player,2026,1,'{}',now())"),{'player':player})
            try:
                _run_alembic(url,'downgrade','0120_player_game_history')
            except RuntimeError as exc:
                assert 'retaining history' in str(exc)
            else:
                raise AssertionError('Pregame history must prevent destructive downgrade')
            print(_run_alembic(url,'check').strip())
            print('PASS full-history 0119/0121 migrations, existing value preservation, no fabricated backfill, unused downgrade/re-upgrade, actual and pregame history rollback guards and model parity')
        finally:
            engine.dispose()

if __name__ == '__main__':
    main()
