import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LoanDetailsCreate(BaseModel):
    principal_amount: Decimal
    interest_rate: Decimal
    rate_period: str = "annual"  # annual, monthly
    amortization_system: str  # sac, price
    term_months: int
    start_date: date
    insurance_monthly: Optional[Decimal] = None
    admin_fee_monthly: Optional[Decimal] = None
    payment_category_id: Optional[uuid.UUID] = None


class LoanDetailsRead(LoanDetailsCreate):
    id: uuid.UUID
    account_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LoanInstallmentRead(BaseModel):
    id: uuid.UUID
    installment_number: int
    due_date: date
    amortization_amount: Decimal
    interest_amount: Decimal
    insurance_amount: Decimal
    admin_fee_amount: Decimal
    total_amount: Decimal
    outstanding_balance_after: Decimal
    status: str
    paid_date: Optional[date] = None
    transaction_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)


class LoanInstallmentUpdate(BaseModel):
    status: Optional[str] = None
    paid_date: Optional[date] = None


class LoanSummary(BaseModel):
    details: LoanDetailsRead
    outstanding_balance: Decimal
    installments_paid: int
    installments_total: int
    next_installment: Optional[LoanInstallmentRead] = None


class LoanImportRowError(BaseModel):
    row: int
    message: str


class LoanImportResult(BaseModel):
    created: int
    updated: int
    errors: list[LoanImportRowError] = []
