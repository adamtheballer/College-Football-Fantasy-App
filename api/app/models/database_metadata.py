from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base


class DatabaseMetadata(Base):
    __tablename__ = "database_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
