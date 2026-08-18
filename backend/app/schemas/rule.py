# backend/app/schemas/rule.py
import datetime
import uuid
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RuleCondition(BaseModel):
    field: str   # description, notes, amount, type, account_id, payee_id, date
    op: str      # contains, not_contains, equals, not_equals, starts_with, ends_with, regex, gt, gte, lt, lte
    value: Any   # str or number depending on field

    @field_validator("value")
    @classmethod
    def value_must_not_be_blank(cls, v: Any) -> Any:
        """Reject blank values — they silently match every transaction.

        A blank value turns `contains`/`starts_with`/`ends_with`/`regex` into a
        tautology, and numeric comparisons fall back to 0, so the rule applies
        its actions to the whole ledger. Explicit `0` and `False` stay valid.
        """
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ValueError("Condition value cannot be blank")
        return v


class RuleConditionGroup(BaseModel):
    """A nested group of conditions joined by its own operator.

    Groups let a rule mix AND and OR — `type is debit AND (contains UBER OR
    contains 99POP)`. They hold leaf conditions only: `conditions` is typed as
    `list[RuleCondition]`, so a nested group fails validation and rule depth
    stays capped at two levels, which is what the engine and editor support.
    """

    op: str = "or"   # and, or
    conditions: list[RuleCondition]

    @field_validator("op")
    @classmethod
    def op_must_be_and_or(cls, v: str) -> str:
        if v not in ("and", "or"):
            raise ValueError("Condition group operator must be 'and' or 'or'")
        return v

    @field_validator("conditions")
    @classmethod
    def group_must_not_be_empty(cls, v: list[RuleCondition]) -> list[RuleCondition]:
        """An empty group never matches, so it can only make a rule confusing."""
        if not v:
            raise ValueError("Condition group cannot be empty")
        return v


# A rule's condition list mixes leaves and one level of groups. The two shapes
# are disjoint — a leaf has no `conditions`, a group has no `field`/`value` — so
# Pydantic's smart union resolves them without a discriminator.
RuleConditionNode = Union[RuleConditionGroup, RuleCondition]


class RuleAction(BaseModel):
    op: str      # set_category, set_payee, append_notes, ignore
    value: Any   # category UUID str or notes string


class RuleCreate(BaseModel):
    name: str
    conditions_op: str = "and"
    conditions: list[RuleConditionNode]
    actions: list[RuleAction]
    priority: int = 0
    is_active: bool = True
    apply_to_existing: bool = True
    overwrite_existing_categories: bool = False


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    conditions_op: Optional[str] = None
    conditions: Optional[list[RuleConditionNode]] = None
    actions: Optional[list[RuleAction]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    apply_to_existing: Optional[bool] = None
    overwrite_existing_categories: bool = False


class RuleRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    conditions_op: str
    conditions: list[dict]
    actions: list[dict]
    priority: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class RuleMutationResponse(RuleRead):
    """A changed rule plus how many existing transactions it just affected."""

    applied_count: int = 0


class RuleCreateResponse(RuleMutationResponse):
    """A created rule response kept for API compatibility."""


class RuleExportItem(BaseModel):
    name: str
    conditions_op: str = "and"
    conditions: list[RuleConditionNode]
    actions: list[RuleAction]
    priority: int = 0
    is_active: bool = True


class RuleExportPayload(BaseModel):
    format: str = "securo-categorization-rules"
    version: int = 1
    rules: list[RuleExportItem]


class RuleImportRequest(BaseModel):
    payload: RuleExportPayload
    overwrite: bool = False


class RuleImportResponse(BaseModel):
    imported: int
    skipped: int
    overwritten: int


class RulePreviewRequest(BaseModel):
    """A draft rule sent from the editor, before it is saved.

    Only the parts that decide what a rule matches and does are needed —
    name/priority/active play no part in the preview, and an inactive draft is
    still previewed so the user can check it before switching it on.
    """

    conditions_op: str = "and"
    conditions: list[RuleConditionNode]
    actions: list[RuleAction] = []
    overwrite_existing_categories: bool = False
    limit: int = Field(default=20, ge=1, le=100)


class RulePreviewItem(BaseModel):
    """One matched transaction plus the category the draft rule would leave it in."""

    id: uuid.UUID
    date: datetime.date
    description: str
    # float, not Decimal: this is display data for the editor's preview table,
    # and Decimal would serialize as a JSON string the UI has to coerce back.
    amount: float
    currency: str
    type: str
    current_category_id: Optional[uuid.UUID] = None
    current_category_name: Optional[str] = None
    new_category_id: Optional[uuid.UUID] = None
    new_category_name: Optional[str] = None
    # False when the rule matches but leaves the transaction as it is — most
    # often because it already has a category and the draft does not overwrite.
    will_change: bool


class RulePreviewResponse(BaseModel):
    matched: int
    will_change: int
    sample: list[RulePreviewItem]
