import uuid
from datetime import date as _date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.category import Category


class LoanDetails(Base):
    """Fixed characteristics of a `type="loan"` account (financiamento).

    One row per loan account. `LoanInstallment` holds the amortization
    schedule computed from these fields (see loan_service.generate_schedule).
    """

    __tablename__ = "loan_details"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), unique=True
    )
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2))
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=6))
    rate_period: Mapped[str] = mapped_column(String(10), default="annual")  # annual, monthly
    amortization_system: Mapped[str] = mapped_column(String(10))  # sac, price
    term_months: Mapped[int] = mapped_column(SmallInteger)
    start_date: Mapped[_date] = mapped_column(Date)  # due date of installment #1
    insurance_monthly: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=15, scale=2), nullable=True)
    admin_fee_monthly: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=15, scale=2), nullable=True)
    # Category that identifies "this transaction is a loan payment" on this
    # account — used to auto-reconcile incoming transactions against the
    # projected installment schedule (see loan_service.try_reconcile_payment).
    payment_category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    account: Mapped["Account"] = relationship()
    payment_category: Mapped[Optional["Category"]] = relationship()
