"""Read-only player facts audit. Exit 2 means actionable source gaps, not DNP."""
import argparse
import json
from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.db.session import SessionLocal
from collegefootballfantasy_api.app.services.player_data_health import player_health
if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--season',type=int,default=settings.current_season_year)
    args=parser.parse_args()
    ensure_models_registered()
    with SessionLocal() as db:
        report=player_health(db,args.season)
        print(json.dumps(report.model_dump(mode='json'),indent=2))
        raise SystemExit(2 if report.status == 'attention' else 0)
