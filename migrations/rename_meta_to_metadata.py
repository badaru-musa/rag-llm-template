"""Rename meta columns to metadata

Revision ID: 001_rename_meta_to_metadata
Revises: 
Create Date: 2025-08-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_rename_meta_to_metadata'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Rename 'meta' columns to 'metadata' in all tables
    op.alter_column('documents', 'meta', new_column_name='metadata')
    op.alter_column('document_chunks', 'meta', new_column_name='metadata')
    op.alter_column('conversations', 'meta', new_column_name='metadata')
    op.alter_column('chat_messages', 'meta', new_column_name='metadata')
    op.alter_column('user_sessions', 'meta', new_column_name='metadata')


def downgrade():
    # Rename 'metadata' columns back to 'meta'
    op.alter_column('documents', 'metadata', new_column_name='meta')
    op.alter_column('document_chunks', 'metadata', new_column_name='meta')
    op.alter_column('conversations', 'metadata', new_column_name='meta')
    op.alter_column('chat_messages', 'metadata', new_column_name='meta')
    op.alter_column('user_sessions', 'metadata', new_column_name='meta')
