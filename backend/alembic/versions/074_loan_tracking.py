"""add loan_details + loan_installments — financing tracking

A financing is a liability tracked in net worth, not an account: its fixed
characteristics live in `loan_details` (principal, rate, SAC/Price system,
term, optional payment category), and the projected/actual amortization
schedule lives in `loan_installments`, one row per installment.

Payments are reconciled against real transactions on whatever account they
were paid from, by matching `payment_category_id` — so the financing needs
no account of its own, the same way an investment holding doesn't.

Revision ID: 074
Revises: 073
Create Date: 2026-08-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "074"
down_revision: Union[str, None] = "073"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "loan_details",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("principal_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("interest_rate", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("rate_period", sa.String(10), nullable=False, server_default="annual"),
        sa.Column("amortization_system", sa.String(10), nullable=False),
        sa.Column("term_months", sa.SmallInteger(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("insurance_monthly", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("admin_fee_monthly", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column(
            "payment_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_loan_details_workspace_id", "loan_details", ["workspace_id"])

    op.create_table(
        "loan_installments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "loan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("loan_details.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("installment_number", sa.SmallInteger(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amortization_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("interest_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("insurance_amount", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"),
        sa.Column("admin_fee_amount", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("outstanding_balance_after", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="projected"),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_loan_installments_loan_id", "loan_installments", ["loan_id"])
    op.create_index("ix_loan_installments_workspace_id", "loan_installments", ["workspace_id"])
    op.create_index("ix_loan_installments_due_date", "loan_installments", ["due_date"])


def downgrade() -> None:
    op.drop_index("ix_loan_installments_due_date", table_name="loan_installments")
    op.drop_index("ix_loan_installments_workspace_id", table_name="loan_installments")
    op.drop_index("ix_loan_installments_loan_id", table_name="loan_installments")
    op.drop_table("loan_installments")

    op.drop_index("ix_loan_details_workspace_id", table_name="loan_details")
    op.drop_table("loan_details")
