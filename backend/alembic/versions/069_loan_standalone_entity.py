"""make loans a standalone entity, not an Account

Financing/loan tracking moves out of the Account model into its own
"Patrimônio" (net worth) entity — a `LoanDetails` no longer has an
`account_id`; it has its own `name` and `currency`. `LoanInstallment`
points at `loan_id` instead of `account_id`. Reconciliation now matches
transactions on *any* account against `payment_category_id`, not just
transactions on a `type="loan"` account.

Backfills `name`/`currency` from the account the loan used to be attached
to (for any rows created while the account-based version of this feature
was live) before dropping the `account_id` columns.

Revision ID: 069
Revises: 068
Create Date: 2026-07-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "069"
down_revision = "068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("loan_details", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("loan_details", sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"))
    op.add_column("loan_details", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"))

    op.execute(
        """
        UPDATE loan_details
        SET name = accounts.name, currency = accounts.currency
        FROM accounts
        WHERE loan_details.account_id = accounts.id
        """
    )
    op.execute("UPDATE loan_details SET name = 'Financiamento' WHERE name IS NULL")
    op.alter_column("loan_details", "name", nullable=False)

    op.add_column(
        "loan_installments",
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("loan_details.id", ondelete="CASCADE"), nullable=True),
    )
    op.execute(
        """
        UPDATE loan_installments
        SET loan_id = loan_details.id
        FROM loan_details
        WHERE loan_installments.account_id = loan_details.account_id
        """
    )
    op.alter_column("loan_installments", "loan_id", nullable=False)
    op.create_index("ix_loan_installments_loan_id", "loan_installments", ["loan_id"])

    op.drop_index("ix_loan_installments_account_id", table_name="loan_installments")
    op.drop_column("loan_installments", "account_id")

    op.drop_constraint("loan_details_account_id_fkey", "loan_details", type_="foreignkey")
    op.drop_column("loan_details", "account_id")


def downgrade() -> None:
    op.add_column(
        "loan_details",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True),
    )
    op.add_column(
        "loan_installments",
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index("ix_loan_installments_account_id", "loan_installments", ["account_id"])

    op.drop_index("ix_loan_installments_loan_id", table_name="loan_installments")
    op.drop_column("loan_installments", "loan_id")

    op.drop_column("loan_details", "is_archived")
    op.drop_column("loan_details", "currency")
    op.drop_column("loan_details", "name")
