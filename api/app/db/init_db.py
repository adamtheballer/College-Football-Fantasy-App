from api.app.db.base import Base
from api.app.db.session import engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
