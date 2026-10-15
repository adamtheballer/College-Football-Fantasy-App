"""Local-only browser fixtures. Never accepts a remote or ordinary app database."""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import uuid4

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import hash_password
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.models.game import Game
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.models.weekly_challenge import WeeklyChallenge
from collegefootballfantasy_api.app.schemas.weekly_challenge import ChallengeConfig
from collegefootballfantasy_api.app.services import weekly_challenges as service


def main():
    url = urlsplit(settings.database_url)
    if settings.is_production or url.hostname not in {"127.0.0.1", "localhost"} or not url.path.startswith("/cff_challenges_"):
        raise SystemExit("Refusing fixtures outside a dedicated local cff_challenges_* database.")
    ensure_models_registered()
    with SessionLocal() as db:
        if db.query(Game).filter(Game.external_id.like("dev-weekly-challenge-%")).first():
            raise SystemExit("Fixtures already exist; use the existing preview or create a fresh disposable database.")
        users = []
        for name,email,admin in [("Weekly Preview", "weekly-preview@local.example", True), ("Rival Preview", "rival-preview@local.example", False), ("Spectator Preview", "spectator-preview@local.example", False)]:
            u=User(email=email,first_name=name,password_hash=hash_password("ChallengeLocal123!"),api_token=uuid4().hex,is_active=True,is_admin=admin,email_verified_at=datetime.now(timezone.utc))
            db.add(u); users.append(u)
        now=datetime.now(timezone.utc)
        week=service.calendar_matchup_display_week(settings.current_season_year,now)
        kickoff=(now+timedelta(days=(5-now.weekday())%7)).replace(hour=16,minute=0,second=0,microsecond=0)
        if kickoff <= now+timedelta(minutes=10):raise SystemExit("Local fixture slate needs a future Saturday in the current competition week.")
        games=[]
        pairs=[('Alabama','Georgia'),('Ohio State','Michigan'),('LSU','Texas'),('Oregon','USC'),('Clemson','Florida State'),('Miami','North Carolina'),('Ole Miss','Oklahoma'),('Tennessee','Vanderbilt'),('Penn State','Wisconsin'),('Utah','BYU'),('Auburn','Arkansas'),('Virginia Tech','Pittsburgh')]
        for i,(home,away) in enumerate(pairs):
            g=Game(external_id=f'dev-weekly-challenge-{i}',season=settings.current_season_year,week=week,season_type='regular',schedule_status='scheduled',start_date=kickoff+timedelta(minutes=i*15),home_team=home,away_team=away)
            db.add(g);games.append(g)
        players=[]
        for i,pos in enumerate(['QB','RB','WR','TE','RB','QB','WR']):
            p=Player(name=f'Dev {pos} Athlete {i+1}',position=pos,school='Alabama',sheet_source_sheet_id=f'canonical-correction:{settings.current_season_year}:local-challenge-fixture-{i}',sheet_projected_season_points=100);db.add(p);players.append(p)
        db.commit()
        r=service.ensure_round(db,settings.current_season_year,week);db.commit()
        for c in db.query(WeeklyChallenge).filter_by(round_id=r.id).all():
            if c.kind=='lock':continue  # Exercise actual administrator publishing in the browser.
            n=12 if c.kind=='slate12' else 5 if c.kind=='duels' else 3 if c.kind=='upset' else 1
            config=ChallengeConfig(expected_version=0,game_ids=[g.id for g in games[:n]],player_ids=[p.id for p in players] if c.kind=='fantasy5' else [],featured_game_id=games[0].id if c.kind=='slate12' else None,underdogs=[{'game_id':g.id,'team':g.away_team,'points':i+1} for i,g in enumerate(games[:3])] if c.kind=='upset' else [])
            service.configure(db,c,config,users[0].id);service.publish(db,c,c.version,users[0].id)
        print(f'Local-only preview ready: season {r.season}, week {r.week}, round {r.id}; 4 published, Lock awaits admin publication.')


if __name__=='__main__':main()
