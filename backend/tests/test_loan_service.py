from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.rule import Rule
from app.models.transaction import Transaction
from app.models.account import Account
from app.schemas.loan import LoanDetailsCreate
from app.services import loan_service, rule_service, transaction_service


def test_monthly_rate_annual_conversion():
    # (1.01)^12 - 1 ≈ 0.126825 -> annual rate ~12.6825% converts back to ~1%/month
    annual = Decimal("0.126825")
    monthly = loan_service.monthly_rate(annual, "annual")
    assert abs(monthly - Decimal("0.01")) < Decimal("0.0001")


def test_monthly_rate_monthly_passthrough():
    rate = Decimal("0.0123")
    assert loan_service.monthly_rate(rate, "monthly") == rate


def test_sac_schedule_amortization_is_constant_and_balance_zeroes_out():
    principal = Decimal("120000")
    i_month = Decimal("0.01")
    term = 12
    rows = loan_service.generate_schedule(
        principal, i_month, term, "sac", date(2026, 1, 10), None, None
    )
    assert len(rows) == term
    expected_amort = (principal / term).quantize(Decimal("0.01"))
    for row in rows[:-1]:
        assert row["amortization_amount"] == expected_amort
    interests = [r["interest_amount"] for r in rows]
    assert interests == sorted(interests, reverse=True)
    assert rows[-1]["outstanding_balance_after"] == Decimal("0.00")
    assert sum(r["amortization_amount"] for r in rows) == principal


def test_price_schedule_installment_is_flat_and_balance_zeroes_out():
    principal = Decimal("120000")
    i_month = Decimal("0.01")
    term = 12
    rows = loan_service.generate_schedule(
        principal, i_month, term, "price", date(2026, 1, 10), None, None
    )
    assert len(rows) == term
    totals = [r["amortization_amount"] + r["interest_amount"] for r in rows[:-1]]
    assert len(set(totals)) == 1
    assert rows[-1]["outstanding_balance_after"] == Decimal("0.00")
    assert sum(r["amortization_amount"] for r in rows) == principal


def test_sac_vs_price_same_inputs_same_total_amortization_different_interest():
    principal = Decimal("120000")
    i_month = Decimal("0.01")
    term = 12
    sac = loan_service.generate_schedule(principal, i_month, term, "sac", date(2026, 1, 10), None, None)
    price = loan_service.generate_schedule(principal, i_month, term, "price", date(2026, 1, 10), None, None)
    assert sum(r["amortization_amount"] for r in sac) == sum(r["amortization_amount"] for r in price)
    assert sum(r["interest_amount"] for r in sac) < sum(r["interest_amount"] for r in price)


def test_fees_are_added_on_top_of_amortization_and_interest():
    rows = loan_service.generate_schedule(
        Decimal("12000"), Decimal("0.01"), 12, "sac", date(2026, 1, 10),
        Decimal("50.00"), Decimal("10.00"),
    )
    for row in rows:
        assert row["total_amount"] == (
            row["amortization_amount"] + row["interest_amount"] + Decimal("50.00") + Decimal("10.00")
        )


def _loan_data(**overrides) -> LoanDetailsCreate:
    defaults: dict[str, Any] = dict(
        name="Financiamento Apto",
        currency="BRL",
        principal_amount=Decimal("300000"),
        interest_rate=Decimal("0.105"),
        rate_period="annual",
        amortization_system="sac",
        term_months=360,
        start_date=date(2026, 8, 10),
    )
    defaults.update(overrides)
    return LoanDetailsCreate(**defaults)


@pytest.mark.asyncio
async def test_create_loan_is_a_standalone_entity_not_an_account(
    session: AsyncSession, test_user, test_workspace
):
    summary = await loan_service.create_loan(session, test_workspace.id, test_user.id, _loan_data())

    assert summary.details.name == "Financiamento Apto"
    assert summary.installments_total == 360
    assert summary.installments_paid == 0
    assert summary.outstanding_balance == Decimal("300000")
    assert summary.next_installment is not None
    assert summary.next_installment.installment_number == 1

    # No Account row should have been created for it.
    from sqlalchemy import select
    accounts = (await session.execute(select(Account).where(Account.workspace_id == test_workspace.id))).scalars().all()
    assert accounts == []


@pytest.mark.asyncio
async def test_list_loans_excludes_archived_by_default(session: AsyncSession, test_user, test_workspace):
    summary = await loan_service.create_loan(session, test_workspace.id, test_user.id, _loan_data())
    loans = await loan_service.list_loans(session, test_workspace.id)
    assert len(loans) == 1
    assert loans[0].details.id == summary.details.id


@pytest.mark.asyncio
async def test_update_loan_regenerates_schedule(session: AsyncSession, test_user, test_workspace):
    summary = await loan_service.create_loan(session, test_workspace.id, test_user.id, _loan_data(term_months=12))
    assert summary.installments_total == 12

    updated = await loan_service.update_loan(
        session, test_workspace.id, summary.details.id, _loan_data(term_months=24),
    )
    assert updated is not None
    assert updated.installments_total == 24


@pytest.mark.asyncio
async def test_delete_loan_removes_installments(session: AsyncSession, test_user, test_workspace):
    summary = await loan_service.create_loan(session, test_workspace.id, test_user.id, _loan_data(term_months=6))
    assert await loan_service.delete_loan(session, summary.details.id, test_workspace.id) is True
    assert await loan_service.get_loan_summary(session, summary.details.id, test_workspace.id) is None
    assert await loan_service.list_installments(session, summary.details.id, test_workspace.id) == []


@pytest.mark.asyncio
async def test_reconcile_payment_matches_closest_unpaid_installment_from_any_account(
    session: AsyncSession, test_user, test_workspace
):
    payment_category = Category(user_id=test_user.id, workspace_id=test_workspace.id, name="Moradia")
    session.add(payment_category)
    await session.flush()

    summary = await loan_service.create_loan(
        session, test_workspace.id, test_user.id,
        _loan_data(principal_amount=Decimal("12000"), interest_rate=Decimal("0.01"), rate_period="monthly",
                    term_months=12, payment_category_id=payment_category.id),
    )

    checking = Account(
        user_id=test_user.id, workspace_id=test_workspace.id, name="Conta Corrente",
        type="checking", balance=Decimal("0"), currency="BRL",
    )
    session.add(checking)
    await session.commit()

    transaction = Transaction(
        user_id=test_user.id, workspace_id=test_workspace.id, account_id=checking.id,
        category_id=payment_category.id, description="Parcela financiamento",
        amount=Decimal("1010.00"), currency="BRL", date=date(2026, 1, 12),
        type="debit", source="manual",
    )
    session.add(transaction)
    await session.flush()

    await loan_service.try_reconcile_payment(session, transaction)
    await session.commit()

    installments = await loan_service.list_installments(session, summary.details.id, test_workspace.id)
    first = next(i for i in installments if i.installment_number == 1)
    assert first.status == "paid"
    assert first.transaction_id == transaction.id
    second = next(i for i in installments if i.installment_number == 2)
    assert second.status == "projected"


@pytest.mark.asyncio
async def test_reconcile_payment_ignores_transactions_outside_payment_category(
    session: AsyncSession, test_user, test_workspace
):
    payment_category = Category(user_id=test_user.id, workspace_id=test_workspace.id, name="Moradia")
    other_category = Category(user_id=test_user.id, workspace_id=test_workspace.id, name="Mercado")
    session.add_all([payment_category, other_category])
    await session.flush()

    summary = await loan_service.create_loan(
        session, test_workspace.id, test_user.id,
        _loan_data(principal_amount=Decimal("12000"), interest_rate=Decimal("0.01"), rate_period="monthly",
                    term_months=12, payment_category_id=payment_category.id),
    )

    checking = Account(
        user_id=test_user.id, workspace_id=test_workspace.id, name="Conta Corrente",
        type="checking", balance=Decimal("0"), currency="BRL",
    )
    session.add(checking)
    await session.commit()

    transaction = Transaction(
        user_id=test_user.id, workspace_id=test_workspace.id, account_id=checking.id,
        category_id=other_category.id, description="Compras", amount=Decimal("200.00"),
        currency="BRL", date=date(2026, 1, 12), type="debit", source="manual",
    )
    session.add(transaction)
    await session.flush()

    await loan_service.try_reconcile_payment(session, transaction)
    await session.commit()

    installments = await loan_service.list_installments(session, summary.details.id, test_workspace.id)
    assert all(i.status == "projected" for i in installments)


@pytest.mark.asyncio
async def test_update_installment_marks_paid_and_unmarks(session: AsyncSession, test_user, test_workspace):
    summary = await loan_service.create_loan(session, test_workspace.id, test_user.id, _loan_data(term_months=6))
    installments = await loan_service.list_installments(session, summary.details.id, test_workspace.id)
    first = installments[0]
    assert first.status == "projected"

    marked = await loan_service.update_installment(
        session, summary.details.id, first.id, test_workspace.id, "paid", date(2026, 8, 15),
    )
    assert marked is not None
    assert marked.status == "paid"
    assert marked.paid_date == date(2026, 8, 15)

    refetched = await loan_service.list_installments(session, summary.details.id, test_workspace.id)
    assert refetched[0].status == "paid"
    assert refetched[0].paid_date == date(2026, 8, 15)

    unmarked = await loan_service.update_installment(
        session, summary.details.id, first.id, test_workspace.id, "projected", None,
    )
    assert unmarked is not None
    assert unmarked.status == "projected"
    assert unmarked.paid_date is None
    assert unmarked.transaction_id is None

    reloaded_summary = await loan_service.get_loan_summary(session, summary.details.id, test_workspace.id)
    assert reloaded_summary is not None
    assert reloaded_summary.installments_paid == 0


@pytest.mark.asyncio
async def test_update_installment_not_found_returns_none(session: AsyncSession, test_user, test_workspace):
    import uuid as _uuid
    summary = await loan_service.create_loan(session, test_workspace.id, test_user.id, _loan_data(term_months=6))
    result = await loan_service.update_installment(
        session, summary.details.id, _uuid.uuid4(), test_workspace.id, "paid", date(2026, 8, 15),
    )
    assert result is None


@pytest.mark.asyncio
async def test_import_loans_csv_creates_and_updates_by_name(session: AsyncSession, test_user, test_workspace):
    csv_content = (
        "name,principal_amount,interest_rate,rate_period,amortization_system,"
        "term_months,start_date,insurance_monthly,admin_fee_monthly,payment_category_name,currency\n"
        "Financiamento Casa,300000,10.5,annual,sac,360,2026-08-10,45.00,25.00,,BRL\n"
    )
    result = await loan_service.import_loans_csv(session, test_workspace.id, test_user.id, csv_content)
    assert result.created == 1
    assert result.updated == 0
    assert result.errors == []

    # Re-importing the same name updates instead of duplicating.
    result2 = await loan_service.import_loans_csv(session, test_workspace.id, test_user.id, csv_content)
    assert result2.created == 0
    assert result2.updated == 1
    loans = await loan_service.list_loans(session, test_workspace.id)
    assert len(loans) == 1


@pytest.mark.asyncio
async def test_import_loans_csv_reports_row_errors(session: AsyncSession, test_user, test_workspace):
    csv_content = (
        "name,principal_amount,interest_rate,rate_period,amortization_system,"
        "term_months,start_date,insurance_monthly,admin_fee_monthly,payment_category_name,currency\n"
        "Financiamento Ruim,not-a-number,10.5,annual,sac,360,2026-08-10,,,,BRL\n"
    )
    result = await loan_service.import_loans_csv(session, test_workspace.id, test_user.id, csv_content)
    assert result.created == 0
    assert len(result.errors) == 1
    assert result.errors[0].row == 2


# ---------------------------------------------------------------------------
# Reconciliation must also fire on paths that mutate category_id in bulk,
# not just on brand-new transactions — these were the actual gap reported:
# transactions weren't "being pulled in" because bank-sync, recurring bill
# materialization, manual edits, bulk category changes and rule application
# never called try_reconcile_payment.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_update_category_reconciles_loan_payments(
    session: AsyncSession, test_user, test_workspace
):
    payment_category = Category(user_id=test_user.id, workspace_id=test_workspace.id, name="Moradia")
    session.add(payment_category)
    await session.flush()

    summary = await loan_service.create_loan(
        session, test_workspace.id, test_user.id,
        _loan_data(principal_amount=Decimal("12000"), interest_rate=Decimal("0.01"), rate_period="monthly",
                    term_months=12, payment_category_id=payment_category.id),
    )

    checking = Account(
        user_id=test_user.id, workspace_id=test_workspace.id, name="Conta Corrente",
        type="checking", balance=Decimal("0"), currency="BRL",
    )
    session.add(checking)
    await session.commit()

    # Transaction created *without* a category (as if freshly imported and
    # left uncategorized), then bulk-recategorized by the user afterwards.
    transaction = Transaction(
        user_id=test_user.id, workspace_id=test_workspace.id, account_id=checking.id,
        description="Pagamento boleto", amount=Decimal("1010.00"), currency="BRL",
        date=date(2026, 1, 12), type="debit", source="manual",
    )
    session.add(transaction)
    await session.commit()

    installments_before = await loan_service.list_installments(session, summary.details.id, test_workspace.id)
    assert all(i.status == "projected" for i in installments_before)

    await transaction_service.bulk_update_category(
        session, test_workspace.id, [transaction.id], payment_category.id,
    )

    installments_after = await loan_service.list_installments(session, summary.details.id, test_workspace.id)
    paid = [i for i in installments_after if i.status == "paid"]
    assert len(paid) == 1
    assert paid[0].transaction_id == transaction.id


@pytest.mark.asyncio
async def test_update_transaction_category_reconciles_loan_payment(
    session: AsyncSession, test_user, test_workspace
):
    payment_category = Category(user_id=test_user.id, workspace_id=test_workspace.id, name="Moradia")
    session.add(payment_category)
    await session.flush()

    summary = await loan_service.create_loan(
        session, test_workspace.id, test_user.id,
        _loan_data(principal_amount=Decimal("12000"), interest_rate=Decimal("0.01"), rate_period="monthly",
                    term_months=12, payment_category_id=payment_category.id),
    )

    checking = Account(
        user_id=test_user.id, workspace_id=test_workspace.id, name="Conta Corrente",
        type="checking", balance=Decimal("0"), currency="BRL",
    )
    session.add(checking)
    await session.commit()

    transaction = Transaction(
        user_id=test_user.id, workspace_id=test_workspace.id, account_id=checking.id,
        description="Pagamento boleto", amount=Decimal("1010.00"), currency="BRL",
        date=date(2026, 1, 12), type="debit", source="manual",
    )
    session.add(transaction)
    await session.commit()

    from app.schemas.transaction import TransactionUpdate
    await transaction_service.update_transaction(
        session, transaction.id, test_workspace.id, test_user.id,
        TransactionUpdate(category_id=payment_category.id),
    )

    installments = await loan_service.list_installments(session, summary.details.id, test_workspace.id)
    paid = [i for i in installments if i.status == "paid"]
    assert len(paid) == 1
    assert paid[0].transaction_id == transaction.id


@pytest.mark.asyncio
async def test_apply_all_rules_reconciles_loan_payments(
    session: AsyncSession, test_user, test_workspace
):
    payment_category = Category(user_id=test_user.id, workspace_id=test_workspace.id, name="Moradia")
    session.add(payment_category)
    await session.flush()

    summary = await loan_service.create_loan(
        session, test_workspace.id, test_user.id,
        _loan_data(principal_amount=Decimal("12000"), interest_rate=Decimal("0.01"), rate_period="monthly",
                    term_months=12, payment_category_id=payment_category.id),
    )

    checking = Account(
        user_id=test_user.id, workspace_id=test_workspace.id, name="Conta Corrente",
        type="checking", balance=Decimal("0"), currency="BRL",
    )
    session.add(checking)
    await session.commit()

    transaction = Transaction(
        user_id=test_user.id, workspace_id=test_workspace.id, account_id=checking.id,
        description="CAIXA FINANCIAMENTO IMOB", amount=Decimal("1010.00"), currency="BRL",
        date=date(2026, 1, 12), type="debit", source="manual",
    )
    session.add(transaction)

    rule = Rule(
        user_id=test_user.id, workspace_id=test_workspace.id, name="Financiamento",
        conditions_op="and",
        conditions=[{"field": "description", "op": "contains", "value": "FINANCIAMENTO"}],
        actions=[{"op": "set_category", "value": str(payment_category.id)}],
        priority=0, is_active=True,
    )
    session.add(rule)
    await session.commit()

    count = await rule_service.apply_all_rules(session, test_workspace.id)
    assert count == 1

    installments = await loan_service.list_installments(session, summary.details.id, test_workspace.id)
    paid = [i for i in installments if i.status == "paid"]
    assert len(paid) == 1
    assert paid[0].transaction_id == transaction.id


@pytest.mark.asyncio
async def test_reconciliation_self_heals_on_read_with_no_explicit_hook(
    session: AsyncSession, test_user, test_workspace
):
    """The whole point of moving reconciliation to `_ensure_reconciled`: a
    transaction that lands in the payment category through *any* means —
    including a path nobody thought to wire up a hook into — still gets
    picked up, because reading the loan is what triggers the match, not a
    specific write. Simulates that by inserting the transaction directly via
    the ORM, bypassing every service-layer function (manual, import, sync,
    rules, bulk-edit) entirely.
    """
    payment_category = Category(user_id=test_user.id, workspace_id=test_workspace.id, name="Moradia")
    session.add(payment_category)
    await session.flush()

    summary = await loan_service.create_loan(
        session, test_workspace.id, test_user.id,
        _loan_data(principal_amount=Decimal("12000"), interest_rate=Decimal("0.01"), rate_period="monthly",
                    term_months=12, payment_category_id=payment_category.id),
    )

    checking = Account(
        user_id=test_user.id, workspace_id=test_workspace.id, name="Conta Corrente",
        type="checking", balance=Decimal("0"), currency="BRL",
    )
    session.add(checking)
    await session.commit()

    # Raw ORM insert — no transaction_service, no import_service, no hook of
    # any kind. If reconciliation still worked, it would only be because
    # some *other* code path happened to call it, and that's exactly the
    # class of bug this design eliminates.
    transaction = Transaction(
        user_id=test_user.id, workspace_id=test_workspace.id, account_id=checking.id,
        category_id=payment_category.id, description="Parcela financiamento",
        amount=Decimal("1010.00"), currency="BRL", date=date(2026, 1, 12),
        type="debit", source="manual",
    )
    session.add(transaction)
    await session.commit()

    # A plain read — list_loans, exactly what GET /api/loans does.
    loans = await loan_service.list_loans(session, test_workspace.id)
    loan = next(item for item in loans if item.details.id == summary.details.id)
    assert loan.installments_paid == 1

    # Calling it again doesn't double-match the same transaction to a second
    # installment (idempotency).
    loans_again = await loan_service.list_loans(session, test_workspace.id)
    loan_again = next(item for item in loans_again if item.details.id == summary.details.id)
    assert loan_again.installments_paid == 1
