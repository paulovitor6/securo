"""add loan_details + loan_installments — real estate financing tracking

New `type="loan"` account: fixed characteristics live in `loan_details`
(principal, rate, SAC/Price system, term, optional payment category for
reconciliation), and the projected/actual amortization schedule lives in
`loan_installments`, one row per parcela. `Account.type` is a free string
column, so no migration is needed there — "loan" is just a new value.

Revision ID: 068
Revises: 067
Create Date: 2026-07-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


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
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("principal_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("interest_rate", sa.Numeric(10, 6), nullable=False),
        sa.Column("rate_period", sa.String(10), nullable=False, server_default="annual"),
        sa.Column("amortization_system", sa.String(10), nullable=False),
        sa.Column("term_months", sa.SmallInteger(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("insurance_monthly", sa.Numeric(15, 2), nullable=True),
        sa.Column("admin_fee_monthly", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "payment_category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_loan_details_workspace_id", "loan_details", ["workspace_id"])

    op.create_table(
        "loan_installments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
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
        sa.Column("amortization_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("interest_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("insurance_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("admin_fee_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("outstanding_balance_after", sa.Numeric(15, 2), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="projected"),
        sa.Column("paid_date", sa.Date(), nullable=True),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_loan_installments_account_id", "loan_installments", ["account_id"])
    op.create_index("ix_loan_installments_workspace_id", "loan_installments", ["workspace_id"])
    op.create_index("ix_loan_installments_due_date", "loan_installments", ["due_date"])


def downgrade() -> None:
    op.drop_index("ix_loan_installments_due_date", table_name="loan_installments")
    op.drop_index("ix_loan_installments_workspace_id", table_name="loan_installments")
    op.drop_index("ix_loan_installments_account_id", table_name="loan_installments")
    op.drop_table("loan_installments")

    op.drop_index("ix_loan_details_workspace_id", table_name="loan_details")
    op.drop_table("loan_details")
