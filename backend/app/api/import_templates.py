import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.workspace_context import (
    WorkspaceContext,
    current_workspace,
    current_writable_workspace,
)
from app.schemas.import_template import ImportTemplateCreate, ImportTemplateRead, ImportTemplateUpdate
from app.services import import_template_service

router = APIRouter(prefix="/api/import-templates", tags=["import-templates"])


@router.get("", response_model=list[ImportTemplateRead])
async def list_templates(
    account_id: Optional[uuid.UUID] = None,
    ctx: WorkspaceContext = Depends(current_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    return await import_template_service.list_templates(session, ctx.workspace.id, account_id)


@router.post("", response_model=ImportTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: ImportTemplateCreate,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    return await import_template_service.create_template(session, ctx.workspace.id, ctx.user_id, data)


@router.patch("/{template_id}", response_model=ImportTemplateRead)
async def update_template(
    template_id: uuid.UUID,
    data: ImportTemplateUpdate,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    template = await import_template_service.update_template(session, template_id, ctx.workspace.id, data)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import template not found")
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    deleted = await import_template_service.delete_template(session, template_id, ctx.workspace.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import template not found")
