from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from collegefootballfantasy_api.app.models import Base, TimestampMixin


class WaiverClaimAudit(TimestampMixin, Base):
    __tablename__ = "waiver_claim_audits"
    __table_args__ = (
        Index("ix_waiver_claim_audits_claim_id", "waiver_claim_id"),
        Index("ix_waiver_claim_audits_action", "action"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    waiver_claim_id: Mapped[int] = mapped_column(ForeignKey("waiver_claims.id", ondelete="CASCADE"))
    league_id: Mapped[int] = mapped_column(ForeignKey("leagues.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(40))
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
