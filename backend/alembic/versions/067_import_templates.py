"""add import_templates table — saved CSV mapping presets per account

Lets an account save its CSV column mapping/options (date format, flip
amount, inflow/outflow split columns) as a named template so a new
statement from the same bank doesn't need to be re-mapped by hand.

Revision ID: 067
Revises: 066
Create Date: 2026-07-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "067"
down_revision = "066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("column_mapping", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("date_format", sa.String(20), nullable=True),
        sa.Column("flip_amount", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("split_columns", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("inflow_column", sa.String(100), nullable=True),
        sa.Column("outflow_column", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_import_templates_workspace_id", "import_templates", ["workspace_id"])
    op.create_index("ix_import_templates_account_id", "import_templates", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_import_templates_account_id", table_name="import_templates")
    op.drop_index("ix_import_templates_workspace_id", table_name="import_templates")
    op.drop_table("import_templates")
