import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ImportTemplateBase(BaseModel):
    name: str
    column_mapping: dict[str, str] = {}
    date_format: Optional[str] = None
    flip_amount: bool = False
    split_columns: bool = False
    inflow_column: Optional[str] = None
    outflow_column: Optional[str] = None


class ImportTemplateCreate(ImportTemplateBase):
    account_id: uuid.UUID


class ImportTemplateUpdate(BaseModel):
    name: Optional[str] = None
    column_mapping: Optional[dict[str, str]] = None
    date_format: Optional[str] = None
    flip_amount: Optional[bool] = None
    split_columns: Optional[bool] = None
    inflow_column: Optional[str] = None
    outflow_column: Optional[str] = None


class ImportTemplateRead(ImportTemplateBase):
    id: uuid.UUID
    account_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
