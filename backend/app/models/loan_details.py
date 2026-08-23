import uuid
from datetime import date as _date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.loan_installment import LoanInstallment


class LoanDetails(Base):
    """A financing/loan liability tracked in net worth ("Patrimônio").

    Standalone entity — not an `Account`. Payments are reconciled against
    real transactions (on whatever checking account they were paid from) by
    matching `payment_category_id`, the same way an investment application
    is a one-sided transaction reconciled against the Assets side (see
    `loan_service.try_reconcile_payment`).
    """

    __tablename__ = "loan_details"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    principal_amount: Mapped[Decimal] = mapped_column(Numeric(precision=15, scale=2))
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=6))
    rate_period: Mapped[str] = mapped_column(String(10), default="annual")  # annual, monthly
    amortization_system: Mapped[str] = mapped_column(String(10))  # sac, price
    term_months: Mapped[int] = mapped_column(SmallInteger)
    start_date: Mapped[_date] = mapped_column(Date)  # due date of installment #1
    insurance_monthly: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=15, scale=2), nullable=True)
    admin_fee_monthly: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=15, scale=2), nullable=True)
    # Category that identifies "this transaction is a loan payment" — used to
    # auto-reconcile incoming transactions (on any account) against the
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

    payment_category: Mapped[Optional["Category"]] = relationship()
    installments: Mapped[list["LoanInstallment"]] = relationship(cascade="all, delete-orphan")
