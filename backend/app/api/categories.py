import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.workspace_context import (
    WorkspaceContext,
    current_workspace,
    current_writable_workspace,
)
from app.schemas.category import (
    CategoryCreate,
    CategoryImportRequest,
    CategoryImportResponse,
    CategoryRead,
    CategoryUpdate,
)
from app.services import category_service

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("/export")
async def export_categories(
    ctx: WorkspaceContext = Depends(current_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    payload = await category_service.export_categories(session, ctx.workspace.id)
    return JSONResponse(
        content=payload.model_dump(mode="json"),
        headers={
            "Content-Disposition": 'attachment; filename="securo-categories.json"',
        },
    )


@router.post("/import", response_model=CategoryImportResponse)
async def import_categories(
    data: CategoryImportRequest,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    return await category_service.import_categories(
        session,
        ctx.workspace.id,
        ctx.user_id,
        data.payload,
        overwrite=data.overwrite,
    )


@router.get("", response_model=list[CategoryRead])
async def list_categories(
    ctx: WorkspaceContext = Depends(current_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    return await category_service.get_categories(session, ctx.workspace.id)


@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    return await category_service.create_category(session, ctx.workspace.id, ctx.user_id, data)


@router.patch("/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: uuid.UUID,
    data: CategoryUpdate,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    category = await category_service.update_category(session, category_id, ctx.workspace.id, data)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    deleted = await category_service.delete_category(session, category_id, ctx.workspace.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
