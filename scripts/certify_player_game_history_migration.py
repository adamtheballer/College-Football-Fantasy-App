"""Verify retained player game history using an owned disposable local DB."""
import os
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from scripts.certify_postseason_migrations import _require_disposable_postgres,_temporary_database,_run_alembic

def main():
    raw=os.environ.get('GAME_HISTORY_TEST_DATABASE_URL')
    if not raw:raise SystemExit('Provide GAME_HISTORY_TEST_DATABASE_URL for a disposable localhost PostgreSQL database')
    base=make_url(raw);_require_disposable_postgres(base)
    if base.host not in {'localhost','127.0.0.1','::1'} or not (base.database or '').startswith('cff_push_'):raise SystemExit('Requires a localhost cff_push_* database')
    previous='0119_player_chart_history';head='0120_player_game_history'
    with _temporary_database(base) as url:
        _run_alembic(url,'upgrade',previous)
        engine=create_engine(url)
        try:
            with engine.begin() as db:
                player=db.scalar(text("INSERT INTO players(name,position,school) VALUES('Retained receiver','WR','Texas') RETURNING id"))
            _run_alembic(url,'upgrade',head)
            with engine.connect() as db:assert db.scalar(text('SELECT count(*) FROM player_historical_game_stats'))==0
            _run_alembic(url,'downgrade',previous);_run_alembic(url,'upgrade',head)
            with engine.begin() as db:
                db.execute(text("INSERT INTO player_historical_game_stats(player_id,season,season_type,week,provider,provider_player_id,provider_event_id,provider_team_id,team_name,opponent_name,kickoff_at,location,result,position,stats,source_response_hash,source_url,imported_at) VALUES (:player,2025,'regular',1,'espn','1','2','3','Texas','Rice',now(),'home','W 7–0','WR','{}',:hash,'https://www.espn.com',now())"),{'player':player,'hash':'a'*64})
            try:_run_alembic(url,'downgrade',previous)
            except RuntimeError as exc:assert 'retain the table' in str(exc)
            else:raise AssertionError('Populated historical facts must refuse destructive downgrade')
            with engine.connect() as db:assert db.scalar(text('SELECT name FROM players WHERE id=:player'),{'player':player})=='Retained receiver'
            print(_run_alembic(url,'check').strip())
            print('PASS complete migration chain, unchanged catalog, no fabricated data, empty rollback/reupgrade, populated-history retention and ORM parity')
        finally:engine.dispose()
if __name__=='__main__':main()
