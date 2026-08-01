import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.account import Account


class ImportTemplate(Base):
    """A saved CSV column-mapping/options preset for one account.

    Lets a user re-run a new statement from the same bank through the import
    page without re-mapping columns every time — mirrors the shape of the
    per-request options already accepted by `import_service.parse_csv`.
    """

    __tablename__ = "import_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    column_mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    date_format: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    flip_amount: Mapped[bool] = mapped_column(Boolean, default=False)
    split_columns: Mapped[bool] = mapped_column(Boolean, default=False)
    inflow_column: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    outflow_column: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Explicit column separator (`,`, `;`, tab, `|`). Null means "keep
    # auto-detecting" — most banks are fine with the sniffer, this is only
    # needed for the ambiguous ones.
    delimiter: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    account: Mapped["Account"] = relationship()
