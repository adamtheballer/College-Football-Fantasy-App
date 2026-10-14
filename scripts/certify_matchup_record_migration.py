"""Certify additive record receipts against an owned disposable localhost PG DB."""
import os
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from scripts.certify_postseason_migrations import _require_disposable_postgres,_run_alembic,_temporary_database


def main():
    raw=os.environ.get('RECORD_TEST_DATABASE_URL')
    if not raw: raise SystemExit('Set RECORD_TEST_DATABASE_URL to an owned disposable localhost PostgreSQL database')
    base=make_url(raw);_require_disposable_postgres(base)
    if base.host not in {'localhost','127.0.0.1','::1'} or not (base.database or '').startswith('cff_push_'):
        raise SystemExit('Requires localhost and cff_push_* database')
    with _temporary_database(base) as url:
        _run_alembic(url,'upgrade','0121_player_chart_forecast')
        engine=create_engine(url)
        try:
            with engine.begin() as db:
                league=db.scalar(text("INSERT INTO leagues (name,platform,scoring_type,season_year,max_teams,status) VALUES ('Record migration','custom','espn_full_ppr',2026,2,'post_draft') RETURNING id"))
                home=db.scalar(text("INSERT INTO teams (league_id,name) VALUES (:league,'Home') RETURNING id"),{'league':league})
                away=db.scalar(text("INSERT INTO teams (league_id,name) VALUES (:league,'Away') RETURNING id"),{'league':league})
                db.execute(text("INSERT INTO matchups (league_id,season,week,home_team_id,away_team_id,status,home_score,away_score) VALUES (:league,2026,1,:home,:away,'final',12,6)"),{'league':league,'home':home,'away':away})
                for team,wins,losses in [(home,1,0),(away,0,1)]:
                    db.execute(text('INSERT INTO standings (league_id,team_id,season,week,wins,losses,ties,points_for,points_against) VALUES (:league,:team,2026,1,:wins,:losses,0,:pf,:pa)'),{'league':league,'team':team,'wins':wins,'losses':losses,'pf':12 if wins else 6,'pa':6 if wins else 12})
            _run_alembic(url,'upgrade','head')
            with engine.connect() as db:
                assert db.scalar(text('SELECT record_application_fingerprint FROM matchups')) is None
                assert db.scalar(text('SELECT home_score FROM matchups'))==12
                assert db.scalar(text('SELECT sum(wins) FROM standings'))==1
                assert db.scalar(text('SELECT sum(losses) FROM standings'))==1
            with engine.begin() as db: db.execute(text('UPDATE matchups SET record_application_fingerprint=:receipt'),{'receipt':'a'*64})
            _run_alembic(url,'downgrade','0121_player_chart_forecast')
            _run_alembic(url,'upgrade','head')
            with engine.connect() as db:
                assert db.scalar(text('SELECT record_application_fingerprint FROM matchups')) is None
                assert db.scalar(text('SELECT home_score FROM matchups'))==12
                assert db.scalar(text('SELECT sum(wins) FROM standings'))==1
            print(_run_alembic(url,'check').strip())
            print('PASS 0122 full-chain upgrade, scores/records preserved, no fabricated legacy receipt, downgrade/re-upgrade and ORM parity')
        finally: engine.dispose()

if __name__=='__main__':main()
