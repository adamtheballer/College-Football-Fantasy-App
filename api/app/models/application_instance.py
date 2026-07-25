from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base


class ApplicationInstance(Base):
    __tablename__ = "application_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_uuid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
