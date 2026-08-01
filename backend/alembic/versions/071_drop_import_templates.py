"""drop import_templates — saved CSV mapping presets removed

The per-account import template feature (added in 067, extended in 070)
didn't earn its keep in practice, so the whole thing is going away.

Dropped rather than deleting migrations 067/070 so any database that
already ran them stays on a walkable chain — same reasoning as 069, which
reshaped 068's tables instead of editing 068 in place.

`downgrade()` recreates the table (with 070's `delimiter` column already
present) so the chain stays reversible, but it comes back empty: the rows
are gone for good once this runs.

Revision ID: 071
Revises: 070
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_import_templates_account_id", table_name="import_templates")
    op.drop_index("ix_import_templates_workspace_id", table_name="import_templates")
    op.drop_table("import_templates")


def downgrade() -> None:
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
        sa.Column("delimiter", sa.String(1), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_import_templates_workspace_id", "import_templates", ["workspace_id"])
    op.create_index("ix_import_templates_account_id", "import_templates", ["account_id"])
