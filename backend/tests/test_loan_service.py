import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.category import Category
from app.models.loan_installment import LoanInstallment
from app.models.transaction import Transaction
from app.schemas.loan import LoanDetailsCreate
from app.services import loan_service


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
    # SAC: constant amortization of principal/term for every row but the last
    # (which absorbs any rounding residue).
    expected_amort = (principal / term).quantize(Decimal("0.01"))
    for row in rows[:-1]:
        assert row["amortization_amount"] == expected_amort
    # Interest is strictly decreasing (declining balance).
    interests = [r["interest_amount"] for r in rows]
    assert interests == sorted(interests, reverse=True)
    # Balance hits exactly zero on the last installment.
    assert rows[-1]["outstanding_balance_after"] == Decimal("0.00")
    # Total amortization across the schedule reconstructs the principal.
    assert sum(r["amortization_amount"] for r in rows) == principal


def test_price_schedule_installment_is_flat_and_balance_zeroes_out():
    principal = Decimal("120000")
    i_month = Decimal("0.01")
    term = 12
    rows = loan_service.generate_schedule(
        principal, i_month, term, "price", date(2026, 1, 10), None, None
    )
    assert len(rows) == term
    # Price: total installment (amortization + interest) is flat except for
    # the last row, which absorbs rounding.
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
    # Both fully amortize the same principal...
    assert sum(r["amortization_amount"] for r in sac) == sum(r["amortization_amount"] for r in price)
    # ...but SAC front-loads amortization, so it pays strictly less total interest.
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


@pytest.mark.asyncio
async def test_create_or_replace_loan_generates_schedule_and_sets_account_type(
    session: AsyncSession, test_user, test_workspace
):
    account = Account(
        id=uuid.uuid4(),
        user_id=test_user.id,
        workspace_id=test_workspace.id,
        name="Financiamento Apto",
        type="checking",
        balance=Decimal("0"),
        currency="BRL",
    )
    session.add(account)
    await session.commit()

    details = await loan_service.create_or_replace_loan(
        session, test_workspace.id, test_user.id, account.id,
        LoanDetailsCreate(
            principal_amount=Decimal("300000"),
            interest_rate=Decimal("0.105"),
            rate_period="annual",
            amortization_system="sac",
            term_months=360,
            start_date=date(2026, 8, 10),
        ),
    )
    assert details.amortization_system == "sac"

    await session.refresh(account)
    assert account.type == "loan"
    assert account.balance == Decimal("300000.00")

    summary = await loan_service.get_loan_summary(session, account.id, test_workspace.id)
    assert summary is not None
    assert summary.installments_total == 360
    assert summary.installments_paid == 0
    assert summary.outstanding_balance == Decimal("300000")
    assert summary.next_installment is not None
    assert summary.next_installment.installment_number == 1


@pytest.mark.asyncio
async def test_reconcile_payment_matches_closest_unpaid_installment(
    session: AsyncSession, test_user, test_workspace
):
    payment_category = Category(
        user_id=test_user.id, workspace_id=test_workspace.id, name="Moradia",
    )
    session.add(payment_category)
    await session.flush()

    account = Account(
        id=uuid.uuid4(), user_id=test_user.id, workspace_id=test_workspace.id,
        name="Financiamento", type="checking", balance=Decimal("0"), currency="BRL",
    )
    session.add(account)
    await session.commit()

    await loan_service.create_or_replace_loan(
        session, test_workspace.id, test_user.id, account.id,
        LoanDetailsCreate(
            principal_amount=Decimal("12000"),
            interest_rate=Decimal("0.01"),
            rate_period="monthly",
            amortization_system="sac",
            term_months=12,
            start_date=date(2026, 1, 10),
            payment_category_id=payment_category.id,
        ),
    )
    await session.refresh(account)
    assert account.type == "loan"

    transaction = Transaction(
        user_id=test_user.id, workspace_id=test_workspace.id, account_id=account.id,
        category_id=payment_category.id, description="Parcela financiamento",
        amount=Decimal("1010.00"), currency="BRL", date=date(2026, 1, 12),
        type="debit", source="manual",
    )
    session.add(transaction)
    await session.flush()

    await loan_service.try_reconcile_payment(session, account, transaction)
    await session.commit()

    installments = await loan_service.list_installments(session, account.id, test_workspace.id)
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

    account = Account(
        id=uuid.uuid4(), user_id=test_user.id, workspace_id=test_workspace.id,
        name="Financiamento", type="checking", balance=Decimal("0"), currency="BRL",
    )
    session.add(account)
    await session.commit()

    await loan_service.create_or_replace_loan(
        session, test_workspace.id, test_user.id, account.id,
        LoanDetailsCreate(
            principal_amount=Decimal("12000"), interest_rate=Decimal("0.01"),
            rate_period="monthly", amortization_system="sac", term_months=12,
            start_date=date(2026, 1, 10), payment_category_id=payment_category.id,
        ),
    )
    await session.refresh(account)

    transaction = Transaction(
        user_id=test_user.id, workspace_id=test_workspace.id, account_id=account.id,
        category_id=other_category.id, description="Compras", amount=Decimal("200.00"),
        currency="BRL", date=date(2026, 1, 12), type="debit", source="manual",
    )
    session.add(transaction)
    await session.flush()

    await loan_service.try_reconcile_payment(session, account, transaction)
    await session.commit()

    installments = await loan_service.list_installments(session, account.id, test_workspace.id)
    assert all(i.status == "projected" for i in installments)


@pytest.mark.asyncio
async def test_import_loans_csv_creates_account_and_schedule(
    session: AsyncSession, test_user, test_workspace
):
    csv_content = (
        "account_name,principal_amount,interest_rate,rate_period,amortization_system,"
        "term_months,start_date,insurance_monthly,admin_fee_monthly,payment_category_name,currency\n"
        "Financiamento Casa,300000,10.5,annual,sac,360,2026-08-10,45.00,25.00,,BRL\n"
    )
    result = await loan_service.import_loans_csv(session, test_workspace.id, test_user.id, csv_content)
    assert result.created == 1
    assert result.updated == 0
    assert result.errors == []


@pytest.mark.asyncio
async def test_import_loans_csv_reports_row_errors(session: AsyncSession, test_user, test_workspace):
    csv_content = (
        "account_name,principal_amount,interest_rate,rate_period,amortization_system,"
        "term_months,start_date,insurance_monthly,admin_fee_monthly,payment_category_name,currency\n"
        "Financiamento Ruim,not-a-number,10.5,annual,sac,360,2026-08-10,,,,BRL\n"
    )
    result = await loan_service.import_loans_csv(session, test_workspace.id, test_user.id, csv_content)
    assert result.created == 0
    assert len(result.errors) == 1
    assert result.errors[0].row == 2
