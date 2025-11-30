"""Add user authentication fields

Revision ID: 20251125_add_user_auth_fields
Revises: normalize_creative_fields
Create Date: 2025-11-25

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251125_add_user_auth_fields'
down_revision = 'normalize_creative_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to users table
    op.add_column('users', sa.Column('external_id', sa.String(length=100), nullable=True))
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('users', sa.Column('credits_usd', sa.Float(), nullable=True, server_default='10.0'))
    
    # Populate external_id from user_id for existing users
    op.execute("UPDATE users SET external_id = user_id WHERE external_id IS NULL")
    
    # Make external_id non-nullable and add unique constraint
    op.alter_column('users', 'external_id', nullable=False)
    op.create_index('ix_users_external_id', 'users', ['external_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_external_id', table_name='users')
    op.drop_column('users', 'credits_usd')
    op.drop_column('users', 'is_admin')
    op.drop_column('users', 'external_id')
