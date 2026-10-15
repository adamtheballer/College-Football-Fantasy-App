"""weekly challenges

Revision ID: 0123_weekly_challenges
Revises: 0122_matchup_record_application
Create Date: 2026-10-15 13:31:56.073153
"""
from alembic import op
import sqlalchemy as sa


revision = '0123_weekly_challenges'
down_revision = '0122_matchup_record_application'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Additive competition tables; canonical users/games/players are reused.
    op.create_table('challenge_rounds',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('week', sa.Integer(), nullable=False),
    sa.Column('rollover_policy', sa.String(length=60), nullable=False),
    sa.Column('next_rollover_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('season', 'week', name='uq_challenge_round_week')
    )
    op.create_table('challenge_recognitions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('round_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['round_id'], ['challenge_rounds.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('round_id', 'user_id', 'code', name='uq_challenge_recognition')
    )
    op.create_index(op.f('ix_challenge_recognitions_round_id'), 'challenge_recognitions', ['round_id'], unique=False)
    op.create_table('weekly_challenges',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('round_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('status', sa.String(length=24), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('rules_version', sa.String(length=50), nullable=False),
    sa.Column('config', sa.JSON(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('lock_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_scored_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('source_hash', sa.String(length=64), nullable=True),
    sa.Column('cancellation_reason', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['round_id'], ['challenge_rounds.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('round_id', 'kind', name='uq_weekly_challenge_kind')
    )
    op.create_index(op.f('ix_weekly_challenges_round_id'), 'weekly_challenges', ['round_id'], unique=False)
    op.create_index('ix_weekly_challenges_settlement', 'weekly_challenges', ['status', 'last_scored_at'], unique=False)
    op.create_table('challenge_audits',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('challenge_id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=30), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['challenge_id'], ['weekly_challenges.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_challenge_audits_challenge_id'), 'challenge_audits', ['challenge_id'], unique=False)
    op.create_table('challenge_duels',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('challenge_id', sa.Integer(), nullable=False),
    sa.Column('inviter_id', sa.Integer(), nullable=False),
    sa.Column('invitee_id', sa.Integer(), nullable=False),
    sa.Column('low_user_id', sa.Integer(), nullable=False),
    sa.Column('high_user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('outcome', sa.String(length=30), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('low_user_id < high_user_id', name='ck_challenge_duel_distinct'),
    sa.ForeignKeyConstraint(['challenge_id'], ['weekly_challenges.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['high_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['invitee_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['inviter_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['low_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('challenge_id', 'low_user_id', 'high_user_id', name='uq_challenge_duel_pair')
    )
    op.create_index(op.f('ix_challenge_duels_challenge_id'), 'challenge_duels', ['challenge_id'], unique=False)
    op.create_table('challenge_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('challenge_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('selections', sa.JSON(), nullable=False),
    sa.Column('tiebreaker', sa.Integer(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['challenge_id'], ['weekly_challenges.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('challenge_id', 'user_id', name='uq_challenge_official_entry')
    )
    op.create_index(op.f('ix_challenge_entries_challenge_id'), 'challenge_entries', ['challenge_id'], unique=False)
    op.create_index('ix_challenge_entries_user', 'challenge_entries', ['user_id', 'challenge_id'], unique=False)
    op.create_table('challenge_pool_players',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('challenge_id', sa.Integer(), nullable=False),
    sa.Column('player_id', sa.Integer(), nullable=False),
    sa.Column('game_id', sa.Integer(), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['challenge_id'], ['weekly_challenges.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['player_id'], ['players.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('challenge_id', 'player_id', name='uq_challenge_pool_player')
    )
    op.create_index(op.f('ix_challenge_pool_players_challenge_id'), 'challenge_pool_players', ['challenge_id'], unique=False)
    op.create_table('challenge_slate_games',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('challenge_id', sa.Integer(), nullable=False),
    sa.Column('game_id', sa.Integer(), nullable=False),
    sa.Column('snapshot', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['challenge_id'], ['weekly_challenges.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('challenge_id', 'game_id', name='uq_challenge_slate_game')
    )
    op.create_index(op.f('ix_challenge_slate_games_challenge_id'), 'challenge_slate_games', ['challenge_id'], unique=False)
    op.create_table('challenge_awards',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entry_id', sa.Integer(), nullable=False),
    sa.Column('round_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('points', sa.Integer(), nullable=False),
    sa.Column('source_hash', sa.String(length=64), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('points >= 0 AND points <= 15', name='ck_challenge_award_points'),
    sa.ForeignKeyConstraint(['entry_id'], ['challenge_entries.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['round_id'], ['challenge_rounds.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entry_id', name='uq_challenge_award_entry')
    )
    op.create_index('ix_challenge_awards_round_user', 'challenge_awards', ['round_id', 'user_id'], unique=False)
    op.create_table('challenge_duel_seats',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('challenge_id', sa.Integer(), nullable=False),
    sa.Column('duel_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['challenge_id'], ['weekly_challenges.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['duel_id'], ['challenge_duels.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('challenge_id', 'user_id', name='uq_challenge_duel_user')
    )
    op.create_index(op.f('ix_challenge_duel_seats_duel_id'), 'challenge_duel_seats', ['duel_id'], unique=False)
    op.create_table('challenge_scores',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entry_id', sa.Integer(), nullable=False),
    sa.Column('raw_points', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('tiebreaker_error', sa.Integer(), nullable=True),
    sa.Column('rank', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('source_hash', sa.String(length=64), nullable=False),
    sa.Column('details', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['entry_id'], ['challenge_entries.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entry_id', name='uq_challenge_score_entry')
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM challenge_rounds)")).scalar():
        raise RuntimeError("Weekly challenge history exists; retain the schema and roll back application code instead.")
    op.drop_table('challenge_scores')
    op.drop_index(op.f('ix_challenge_duel_seats_duel_id'), table_name='challenge_duel_seats')
    op.drop_table('challenge_duel_seats')
    op.drop_index('ix_challenge_awards_round_user', table_name='challenge_awards')
    op.drop_table('challenge_awards')
    op.drop_index(op.f('ix_challenge_slate_games_challenge_id'), table_name='challenge_slate_games')
    op.drop_table('challenge_slate_games')
    op.drop_index(op.f('ix_challenge_pool_players_challenge_id'), table_name='challenge_pool_players')
    op.drop_table('challenge_pool_players')
    op.drop_index('ix_challenge_entries_user', table_name='challenge_entries')
    op.drop_index(op.f('ix_challenge_entries_challenge_id'), table_name='challenge_entries')
    op.drop_table('challenge_entries')
    op.drop_index(op.f('ix_challenge_duels_challenge_id'), table_name='challenge_duels')
    op.drop_table('challenge_duels')
    op.drop_index(op.f('ix_challenge_audits_challenge_id'), table_name='challenge_audits')
    op.drop_table('challenge_audits')
    op.drop_index('ix_weekly_challenges_settlement', table_name='weekly_challenges')
    op.drop_index(op.f('ix_weekly_challenges_round_id'), table_name='weekly_challenges')
    op.drop_table('weekly_challenges')
    op.drop_index(op.f('ix_challenge_recognitions_round_id'), table_name='challenge_recognitions')
    op.drop_table('challenge_recognitions')
    op.drop_table('challenge_rounds')
