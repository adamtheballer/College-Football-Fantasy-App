from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class CollegeTeam(TimestampMixin, Base):
    __tablename__ = "college_teams"
    __table_args__ = (
        UniqueConstraint("name", name="uq_college_teams_name"),
        Index("ix_college_teams_conference", "conference"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    conference: Mapped[str | None] = mapped_column(String(50), nullable=True)

    provider_ids = relationship("TeamProviderId", back_populates="team", cascade="all, delete-orphan")
