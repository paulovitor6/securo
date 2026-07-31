import calendar
import csv
import io
import logging
import uuid
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.loan_details import LoanDetails
from app.models.loan_installment import LoanInstallment
from app.models.transaction import Transaction
from app.schemas.loan import (
    LoanDetailsCreate,
    LoanDetailsRead,
    LoanImportResult,
    LoanImportRowError,
    LoanInstallmentRead,
    LoanSummary,
)

logger = logging.getLogger(__name__)

CENTS = Decimal("0.01")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def _add_months(start: date, months: int) -> date:
    """Add `months` to `start`, clamping the day to the target month's length."""
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def monthly_rate(rate: Decimal, period: str) -> Decimal:
    """Convert a stored interest rate to an effective monthly rate.

    `period="monthly"` returns the rate as-is; `period="annual"` (the
    default) converts an effective annual rate with (1+r)^(1/12) - 1. The
    exponent is fractional, so this step goes through float — the result is
    then used only to seed a schedule of amounts already rounded to cents.
    """
    if period == "monthly":
        return rate
    annual = float(rate)
    monthly = (1 + annual) ** (1 / 12) - 1
    return Decimal(str(monthly))


def generate_schedule(
    principal: Decimal,
    i_month: Decimal,
    term_months: int,
    system: str,
    start_date: date,
    insurance_monthly: Optional[Decimal],
    admin_fee_monthly: Optional[Decimal],
) -> list[dict]:
    """Generate a full SAC or Price amortization schedule.

    SAC: constant amortization (principal / term_months), decreasing total.
    Price (Tabela Price): constant total installment (interest + amortization),
    computed with the standard annuity formula.

    Both round every component to cents as they go and force the final
    installment's amortization to absorb whatever residual is left so the
    outstanding balance lands on exactly zero.
    """
    insurance = insurance_monthly or Decimal("0")
    admin_fee = admin_fee_monthly or Decimal("0")

    if system == "price":
        if i_month == 0:
            fixed_installment = _quantize(principal / term_months)
        else:
            factor = (1 + i_month) ** term_months
            fixed_installment = _quantize(principal * i_month * factor / (factor - 1))
    else:
        constant_amortization = _quantize(principal / term_months)

    rows = []
    outstanding = principal
    for n in range(1, term_months + 1):
        interest = _quantize(outstanding * i_month)
        if n == term_months:
            amortization = outstanding
        elif system == "price":
            amortization = fixed_installment - interest
        else:
            amortization = constant_amortization
        outstanding_after = outstanding - amortization
        total = amortization + interest + insurance + admin_fee
        rows.append({
            "installment_number": n,
            "due_date": _add_months(start_date, n - 1),
            "amortization_amount": amortization,
            "interest_amount": interest,
            "insurance_amount": insurance,
            "admin_fee_amount": admin_fee,
            "total_amount": total,
            "outstanding_balance_after": outstanding_after,
        })
        outstanding = outstanding_after
    return rows


async def _get_details(session: AsyncSession, loan_id: uuid.UUID, workspace_id: uuid.UUID) -> Optional[LoanDetails]:
    result = await session.execute(
        select(LoanDetails).where(LoanDetails.id == loan_id, LoanDetails.workspace_id == workspace_id)
    )
    return result.scalar_one_or_none()


async def _build_summary(session: AsyncSession, details: LoanDetails) -> LoanSummary:
    await _ensure_reconciled(session, details)

    installments_result = await session.execute(
        select(LoanInstallment)
        .where(LoanInstallment.loan_id == details.id)
        .order_by(LoanInstallment.installment_number)
    )
    installments = list(installments_result.scalars().all())

    paid = [i for i in installments if i.status == "paid"]
    next_installment = next((i for i in installments if i.status == "projected"), None)
    outstanding_balance = installments[-1].outstanding_balance_after if installments else details.principal_amount
    if next_installment is not None:
        idx = installments.index(next_installment)
        outstanding_balance = installments[idx - 1].outstanding_balance_after if idx > 0 else details.principal_amount

    return LoanSummary(
        details=LoanDetailsRead.model_validate(details),
        outstanding_balance=outstanding_balance,
        installments_paid=len(paid),
        installments_total=len(installments),
        next_installment=LoanInstallmentRead.model_validate(next_installment) if next_installment else None,
    )


async def list_loans(session: AsyncSession, workspace_id: uuid.UUID, include_archived: bool = False) -> list[LoanSummary]:
    query = select(LoanDetails).where(LoanDetails.workspace_id == workspace_id)
    if not include_archived:
        query = query.where(LoanDetails.is_archived == False)  # noqa: E712
    result = await session.execute(query.order_by(LoanDetails.name))
    return [await _build_summary(session, d) for d in result.scalars().all()]


async def get_loan_summary(session: AsyncSession, loan_id: uuid.UUID, workspace_id: uuid.UUID) -> Optional[LoanSummary]:
    details = await _get_details(session, loan_id, workspace_id)
    if not details:
        return None
    return await _build_summary(session, details)


async def list_installments(
    session: AsyncSession, loan_id: uuid.UUID, workspace_id: uuid.UUID
) -> list[LoanInstallmentRead]:
    details = await _get_details(session, loan_id, workspace_id)
    if details:
        await _ensure_reconciled(session, details)

    result = await session.execute(
        select(LoanInstallment)
        .where(LoanInstallment.loan_id == loan_id, LoanInstallment.workspace_id == workspace_id)
        .order_by(LoanInstallment.installment_number)
    )
    return [LoanInstallmentRead.model_validate(i) for i in result.scalars().all()]


async def _regenerate_schedule(session: AsyncSession, details: LoanDetails) -> None:
    """Wipe and regenerate the installment schedule for a loan from scratch."""
    existing = await session.execute(select(LoanInstallment).where(LoanInstallment.loan_id == details.id))
    for row in existing.scalars().all():
        await session.delete(row)
    await session.flush()

    i_month = monthly_rate(details.interest_rate, details.rate_period)
    rows = generate_schedule(
        details.principal_amount,
        i_month,
        details.term_months,
        details.amortization_system,
        details.start_date,
        details.insurance_monthly,
        details.admin_fee_monthly,
    )
    for row in rows:
        session.add(LoanInstallment(loan_id=details.id, workspace_id=details.workspace_id, **row))


async def create_loan(
    session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID, data: LoanDetailsCreate
) -> LoanSummary:
    details = LoanDetails(
        user_id=user_id,
        workspace_id=workspace_id,
        name=data.name,
        currency=data.currency,
        principal_amount=data.principal_amount,
        interest_rate=data.interest_rate,
        rate_period=data.rate_period,
        amortization_system=data.amortization_system,
        term_months=data.term_months,
        start_date=data.start_date,
        insurance_monthly=data.insurance_monthly,
        admin_fee_monthly=data.admin_fee_monthly,
        payment_category_id=data.payment_category_id,
    )
    session.add(details)
    await session.flush()
    await _regenerate_schedule(session, details)
    await session.commit()
    return await get_loan_summary(session, details.id, workspace_id)


async def update_loan(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    loan_id: uuid.UUID,
    data: LoanDetailsCreate,
) -> Optional[LoanSummary]:
    """Update a loan's characteristics and regenerate its full schedule.

    Editing the loan (rate, term, ...) replaces every installment row —
    paid/projected status isn't merged row by row. Reconciliation re-runs
    afterwards so payment history isn't lost.
    """
    details = await _get_details(session, loan_id, workspace_id)
    if not details:
        return None

    details.name = data.name
    details.currency = data.currency
    details.principal_amount = data.principal_amount
    details.interest_rate = data.interest_rate
    details.rate_period = data.rate_period
    details.amortization_system = data.amortization_system
    details.term_months = data.term_months
    details.start_date = data.start_date
    details.insurance_monthly = data.insurance_monthly
    details.admin_fee_monthly = data.admin_fee_monthly
    details.payment_category_id = data.payment_category_id
    await session.flush()

    await _regenerate_schedule(session, details)
    await session.commit()
    return await get_loan_summary(session, loan_id, workspace_id)


async def delete_loan(session: AsyncSession, loan_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
    details = await _get_details(session, loan_id, workspace_id)
    if not details:
        return False
    await session.delete(details)
    await session.commit()
    return True


async def update_installment(
    session: AsyncSession,
    loan_id: uuid.UUID,
    installment_id: uuid.UUID,
    workspace_id: uuid.UUID,
    status_value: Optional[str],
    paid_date: Optional[date],
) -> Optional[LoanInstallmentRead]:
    result = await session.execute(
        select(LoanInstallment).where(
            LoanInstallment.id == installment_id,
            LoanInstallment.loan_id == loan_id,
            LoanInstallment.workspace_id == workspace_id,
        )
    )
    installment = result.scalar_one_or_none()
    if not installment:
        return None
    if status_value is not None:
        installment.status = status_value
        if status_value != "paid":
            installment.paid_date = None
            installment.transaction_id = None
        elif paid_date is not None:
            installment.paid_date = paid_date
    elif paid_date is not None:
        installment.paid_date = paid_date
    await session.commit()
    await session.refresh(installment)
    return LoanInstallmentRead.model_validate(installment)


async def try_reconcile_payment(session: AsyncSession, transaction: Transaction) -> bool:
    """Match a transaction against the next unpaid installment, if it looks like a loan payment.

    No amount validation — matches the closest-by-date `projected`
    installment of whichever loan (in the same workspace) has this
    transaction's category configured as its payment category. Simple on
    purpose: this is reconciliation, not enforcement.

    Idempotent: a transaction already linked to some installment is left
    alone, so this is safe to call repeatedly over the same transaction
    (which `_ensure_reconciled` does, on every read — see its docstring for
    why reconciliation lives there and not scattered across every write
    path). Returns whether it actually changed anything.
    """
    if transaction.category_id is None:
        return False
    loan_result = await session.execute(
        select(LoanDetails).where(
            LoanDetails.workspace_id == transaction.workspace_id,
            LoanDetails.payment_category_id == transaction.category_id,
        )
    )
    loan = loan_result.scalars().first()
    if loan is None:
        return False

    already_linked = await session.execute(
        select(LoanInstallment.id).where(LoanInstallment.transaction_id == transaction.id)
    )
    if already_linked.scalar_one_or_none() is not None:
        return False

    pending_result = await session.execute(
        select(LoanInstallment)
        .where(LoanInstallment.loan_id == loan.id, LoanInstallment.status == "projected")
        .order_by(LoanInstallment.installment_number)
    )
    pending = list(pending_result.scalars().all())
    if not pending:
        return False

    closest = min(pending, key=lambda i: abs((i.due_date - transaction.date).days))
    closest.status = "paid"
    closest.paid_date = transaction.date
    closest.transaction_id = transaction.id
    return True


async def _ensure_reconciled(session: AsyncSession, details: LoanDetails) -> bool:
    """Read-time reconciliation: match transactions in the payment category
    against still-`projected` installments, every time the loan is read.

    This used to be a write-time side effect triggered from every place a
    transaction's category could end up matching (manual entry, CSV/OFX
    import, bank sync — initial and periodic, recurring-bill materialization,
    a manual re-categorize, a bulk edit, a rule...). That list was never
    actually complete — any new or overlooked write path silently skipped
    reconciliation. Since "is this transaction linked to an installment" is
    just a query over existing rows, it's simpler and strictly more correct
    to compute it whenever the loan is viewed instead of chasing every
    mutation site. Idempotent and cheap enough for this app's scale.
    """
    if not details.payment_category_id:
        return False

    pending_exists = await session.execute(
        select(LoanInstallment.id)
        .where(LoanInstallment.loan_id == details.id, LoanInstallment.status == "projected")
        .limit(1)
    )
    if pending_exists.scalar_one_or_none() is None:
        return False  # fully paid off — nothing left to match

    tx_result = await session.execute(
        select(Transaction)
        .where(Transaction.workspace_id == details.workspace_id, Transaction.category_id == details.payment_category_id)
        .order_by(Transaction.date)
    )
    changed = False
    for transaction in tx_result.scalars().all():
        if await try_reconcile_payment(session, transaction):
            changed = True
    if changed:
        await session.commit()
    return changed


async def import_loans_csv(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    content: str,
) -> LoanImportResult:
    """Import loan characteristics from CSV — one row per loan.

    Columns: name, principal_amount, interest_rate, rate_period,
    amortization_system, term_months, start_date, insurance_monthly,
    admin_fee_monthly, payment_category_name, currency. Finds an existing
    loan by name to update, or creates a new one, and (re)generates its
    schedule either way.
    """
    reader = csv.DictReader(io.StringIO(content))
    reader.fieldnames = [(f or "").strip().lower() for f in (reader.fieldnames or [])]

    loans_result = await session.execute(select(LoanDetails).where(LoanDetails.workspace_id == workspace_id))
    loans_by_name = {d.name.strip().lower(): d for d in loans_result.scalars().all()}

    categories_result = await session.execute(select(Category).where(Category.workspace_id == workspace_id))
    categories_by_name = {c.name.strip().lower(): c.id for c in categories_result.scalars().all()}

    created = 0
    updated = 0
    errors: list[LoanImportRowError] = []

    for i, row in enumerate(reader, start=2):
        try:
            name = (row.get("name") or "").strip()
            if not name:
                raise ValueError("missing name")
            principal_amount = Decimal((row.get("principal_amount") or "").strip())
            interest_rate = Decimal((row.get("interest_rate") or "").strip())
            rate_period = (row.get("rate_period") or "annual").strip().lower() or "annual"
            amortization_system = (row.get("amortization_system") or "").strip().lower()
            if amortization_system not in ("sac", "price"):
                raise ValueError("amortization_system must be sac or price")
            term_months = int((row.get("term_months") or "").strip())
            start_date = date.fromisoformat((row.get("start_date") or "").strip())
            insurance_raw = (row.get("insurance_monthly") or "").strip()
            admin_fee_raw = (row.get("admin_fee_monthly") or "").strip()
            insurance_monthly = Decimal(insurance_raw) if insurance_raw else None
            admin_fee_monthly = Decimal(admin_fee_raw) if admin_fee_raw else None
            payment_category_name = (row.get("payment_category_name") or "").strip()
            payment_category_id = categories_by_name.get(payment_category_name.lower()) if payment_category_name else None
            currency = (row.get("currency") or "").strip() or "BRL"
        except (ValueError, ArithmeticError) as e:
            errors.append(LoanImportRowError(row=i, message=str(e)))
            continue

        data = LoanDetailsCreate(
            name=name,
            currency=currency,
            principal_amount=principal_amount,
            interest_rate=interest_rate,
            rate_period=rate_period,
            amortization_system=amortization_system,
            term_months=term_months,
            start_date=start_date,
            insurance_monthly=insurance_monthly,
            admin_fee_monthly=admin_fee_monthly,
            payment_category_id=payment_category_id,
        )

        key = name.lower()
        existing = loans_by_name.get(key)
        if existing is None:
            summary = await create_loan(session, workspace_id, user_id, data)
            loans_by_name[key] = await _get_details(session, summary.details.id, workspace_id)
            created += 1
        else:
            await update_loan(session, workspace_id, existing.id, data)
            updated += 1

    return LoanImportResult(created=created, updated=updated, errors=errors)
