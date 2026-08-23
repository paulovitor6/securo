import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CategoryBase(BaseModel):
    name: str
    icon: str = "circle-help"
    color: str = "#6B7280"


class CategoryCreate(CategoryBase):
    group_id: Optional[uuid.UUID] = None
    treat_as_transfer: bool = False
    is_ignored: bool = False


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    group_id: Optional[uuid.UUID] = None
    treat_as_transfer: Optional[bool] = None
    is_ignored: Optional[bool] = None


class CategoryRead(CategoryBase):
    id: uuid.UUID
    user_id: uuid.UUID
    group_id: Optional[uuid.UUID] = None
    is_system: bool
    treat_as_transfer: bool = False
    is_ignored: bool = False

    model_config = ConfigDict(from_attributes=True)


class CategoryGroupExportItem(BaseModel):
    name: str
    icon: str = "folder"
    color: str = "#6B7280"
    position: int = 0


class CategoryExportItem(BaseModel):
    name: str
    icon: str = "circle-help"
    color: str = "#6B7280"
    group_name: Optional[str] = None
    treat_as_transfer: bool = False
    is_ignored: bool = False


class CategoryExportPayload(BaseModel):
    format: str = "securo-categories"
    version: int = 1
    groups: list[CategoryGroupExportItem]
    categories: list[CategoryExportItem]


class CategoryImportRequest(BaseModel):
    payload: CategoryExportPayload
    overwrite: bool = False


class CategoryImportResponse(BaseModel):
    groups_created: int
    categories_imported: int
    categories_updated: int
    categories_skipped: int
