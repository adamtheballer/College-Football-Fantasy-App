"""Add permanent mutual rivalry tables.

Revision ID: 0099_permanent_rivalries
Revises: 0098_profile_photo_data
"""

from alembic import op
import sqlalchemy as sa

revision = "0099_permanent_rivalries"
down_revision = "0098_profile_photo_data"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("league_rivalries", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False), sa.Column("team_a_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False), sa.Column("team_b_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="RESTRICT"), nullable=False), sa.Column("user_a_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False), sa.Column("user_b_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False), sa.Column("team_a_name_snapshot", sa.String(200), nullable=False), sa.Column("team_b_name_snapshot", sa.String(200), nullable=False), sa.Column("manager_a_name_snapshot", sa.String(200), nullable=False), sa.Column("manager_b_name_snapshot", sa.String(200), nullable=False), sa.Column("accepted_invite_id", sa.Integer(), nullable=False, unique=True), sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("archived_at", sa.DateTime(timezone=True)), sa.Column("archive_reason", sa.String(300)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("league_id", "team_a_id", "team_b_id", name="uq_league_rivalry_pair"))
    op.create_index("ix_league_rivalries_league_id", "league_rivalries", ["league_id"])
    op.create_table("league_rivalry_invites", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False), sa.Column("sender_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("sender_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False), sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("recipient_team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("responded_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("accepted_rivalry_id", sa.Integer(), sa.ForeignKey("league_rivalries.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_league_rivalry_invites_league_id", "league_rivalry_invites", ["league_id"])
    op.create_index("ix_league_rivalry_invites_league_status", "league_rivalry_invites", ["league_id", "status"])
    op.create_index("ix_league_rivalry_invites_recipient_status", "league_rivalry_invites", ["recipient_team_id", "status"])
    op.create_index("ix_league_rivalry_invites_expires_at", "league_rivalry_invites", ["expires_at"])
    op.create_index("uq_league_rivalry_pending_sender", "league_rivalry_invites", ["league_id", "sender_team_id"], unique=True, postgresql_where=sa.text("status = 'PENDING'"), sqlite_where=sa.text("status = 'PENDING'"))
    op.create_index("uq_league_rivalry_pending_pair", "league_rivalry_invites", ["league_id", "sender_team_id", "recipient_team_id"], unique=True, postgresql_where=sa.text("status = 'PENDING'"), sqlite_where=sa.text("status = 'PENDING'"))
    op.create_table("league_rivalry_bindings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("league_id", sa.Integer(), sa.ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False), sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("rivalry_id", sa.Integer(), sa.ForeignKey("league_rivalries.id", ondelete="CASCADE"), nullable=False), sa.UniqueConstraint("league_id", "team_id", name="uq_league_rivalry_binding_team"))
    op.create_index("ix_league_rivalry_bindings_league_id", "league_rivalry_bindings", ["league_id"])
    op.create_index("ix_league_rivalry_bindings_rivalry_id", "league_rivalry_bindings", ["rivalry_id"])


def downgrade() -> None:
    op.drop_index("ix_league_rivalry_bindings_rivalry_id", table_name="league_rivalry_bindings")
    op.drop_index("ix_league_rivalry_bindings_league_id", table_name="league_rivalry_bindings")
    op.drop_table("league_rivalry_bindings")
    op.drop_index("uq_league_rivalry_pending_pair", table_name="league_rivalry_invites")
    op.drop_index("uq_league_rivalry_pending_sender", table_name="league_rivalry_invites")
    op.drop_index("ix_league_rivalry_invites_expires_at", table_name="league_rivalry_invites")
    op.drop_index("ix_league_rivalry_invites_recipient_status", table_name="league_rivalry_invites")
    op.drop_index("ix_league_rivalry_invites_league_status", table_name="league_rivalry_invites")
    op.drop_index("ix_league_rivalry_invites_league_id", table_name="league_rivalry_invites")
    op.drop_table("league_rivalry_invites")
    op.drop_index("ix_league_rivalries_league_id", table_name="league_rivalries")
    op.drop_table("league_rivalries")
