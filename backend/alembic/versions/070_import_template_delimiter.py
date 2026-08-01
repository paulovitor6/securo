"""add delimiter to import_templates — explicit CSV separator per template

Revision ID: 070
Revises: 069
Create Date: 2026-07-31
"""

import sqlalchemy as sa
from alembic import op

revision = "070"
down_revision = "069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("import_templates", sa.Column("delimiter", sa.String(1), nullable=True))


def downgrade() -> None:
    op.drop_column("import_templates", "delimiter")
