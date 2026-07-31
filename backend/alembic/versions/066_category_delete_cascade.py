"""allow deleting categories in use (issue: editable/deletable default categories)

Categories (including default `is_system=True` ones) can now be deleted even when
referenced elsewhere. Before this, `transactions.category_id`, `budgets.category_id`
and `recurring_transactions.category_id` had no `ondelete`, so Postgres defaulted to
`NO ACTION` and deleting an in-use category raised a FK violation:
- transactions.category_id            -> ON DELETE SET NULL (tx becomes uncategorized)
- recurring_transactions.category_id  -> ON DELETE SET NULL
- budgets.category_id                 -> ON DELETE CASCADE (a budget without a
  category doesn't make sense; the frontend warns before deleting a category that has
  budgets attached)

Revision ID: 066
Revises: 065
Create Date: 2026-07-31
"""

from alembic import op

revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "transactions_category_id_fkey", "transactions", type_="foreignkey"
    )
    op.create_foreign_key(
        "transactions_category_id_fkey",
        "transactions",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "recurring_transactions_category_id_fkey",
        "recurring_transactions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "recurring_transactions_category_id_fkey",
        "recurring_transactions",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "budgets_category_id_fkey", "budgets", type_="foreignkey"
    )
    op.create_foreign_key(
        "budgets_category_id_fkey",
        "budgets",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "budgets_category_id_fkey", "budgets", type_="foreignkey"
    )
    op.create_foreign_key(
        "budgets_category_id_fkey",
        "budgets",
        "categories",
        ["category_id"],
        ["id"],
    )

    op.drop_constraint(
        "recurring_transactions_category_id_fkey",
        "recurring_transactions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "recurring_transactions_category_id_fkey",
        "recurring_transactions",
        "categories",
        ["category_id"],
        ["id"],
    )

    op.drop_constraint(
        "transactions_category_id_fkey", "transactions", type_="foreignkey"
    )
    op.create_foreign_key(
        "transactions_category_id_fkey",
        "transactions",
        "categories",
        ["category_id"],
        ["id"],
    )
