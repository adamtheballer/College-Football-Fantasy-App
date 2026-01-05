from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class League(TimestampMixin, Base):
    __tablename__ = "leagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=False, index=True)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    scoring_type: Mapped[str] = mapped_column(String(50))

    teams = relationship("Team", back_populates="league", cascade="all, delete-orphan")
