from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from api.app.models import Base


class MockDraftEvent(Base):
    __tablename__ = "mock_draft_events"
    __table_args__ = (
        Index("ix_mock_draft_events_session_id_id", "session_id", "id"),
        Index("ix_mock_draft_events_session_id_occurred_at", "session_id", "occurred_at"),
        Index("ix_mock_draft_events_event_type", "event_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("mock_draft_sessions.id", ondelete="CASCADE"))
    mock_draft_id: Mapped[int | None] = mapped_column(ForeignKey("mock_draft_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(String(120))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
