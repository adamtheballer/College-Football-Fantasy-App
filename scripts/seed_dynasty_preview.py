"""Synthetic browser QA data. Refuses remote DBs and production environments."""

import os

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from collegefootballfantasy_api.app.core.config import settings
from collegefootballfantasy_api.app.core.security import hash_password
from collegefootballfantasy_api.app.db.base import Base
from collegefootballfantasy_api.app.db.model_registry import ensure_models_registered
from collegefootballfantasy_api.app.models.player import Player
from collegefootballfantasy_api.app.models.user import User
from collegefootballfantasy_api.app.schemas.dynasty import DynastyCatalogFact
from collegefootballfantasy_api.app.services.dynasty import review_catalog


def main():
    raw = os.environ.get("DYNASTY_DISPOSABLE_DATABASE_URL", "")
    url = make_url(raw)
    if (
        settings.is_production
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database != "dynasty"
    ):
        raise SystemExit(
            "Requires a local disposable database named dynasty; production is forbidden"
        )
    ensure_models_registered()
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for i in range(2):
            email = f"dynasty-qa-{i}@example.invalid"
            if db.scalar(select(User).where(User.email == email)) is None:
                db.add(
                    User(
                        first_name=f"Dynasty QA {i}",
                        email=email,
                        password_hash=hash_password("DynastyPreview2027!"),
                        api_token=f"disposable-dynasty-qa-{i}",
                        is_admin=i == 0,
                    )
                )
        db.flush()
        facts = []
        for i in range(20):
            name = f"Dynasty QA Prospect {i:02}"
            player = db.scalar(select(Player).where(Player.name == name))
            if player is None:
                player = Player(name=name, school="Arizona State", position="RB")
                db.add(player)
                db.flush()
            year = 2027 if i < 10 else 2028
            facts.append(
                DynastyCatalogFact(
                    player_id=player.id,
                    season=year,
                    entry_season=2026 if i < 10 else year,
                    school="Arizona State",
                    academic_class="SO" if i < 10 else "FR",
                    eligible=True,
                    source_url=f"https://example.edu/synthetic-qa/{year}",
                    base_value=80 - i,
                )
            )
        review_catalog(db, facts)
        db.commit()
    engine.dispose()
    print(
        "Seeded two synthetic QA accounts and 20 fictional season facts in local dynasty database."
    )


if __name__ == "__main__":
    main()
