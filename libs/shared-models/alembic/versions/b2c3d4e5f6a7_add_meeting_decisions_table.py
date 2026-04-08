"""Add meeting_decisions table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'meeting_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('meeting_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('speaker', sa.String(255), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('entities', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['meeting_id'], ['meetings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_meeting_decisions_id', 'meeting_decisions', ['id'])
    op.create_index('ix_meeting_decisions_meeting_id', 'meeting_decisions', ['meeting_id'])
    op.create_index('ix_meeting_decisions_created_at', 'meeting_decisions', ['created_at'])
    op.create_index('ix_meeting_decisions_meeting_created', 'meeting_decisions', ['meeting_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('meeting_decisions')
