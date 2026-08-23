import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.workspace_context import (
    WorkspaceContext,
    current_workspace,
    current_writable_workspace,
)
from app.schemas.loan import (
    LoanDetailsCreate,
    LoanImportResult,
    LoanInstallmentRead,
    LoanInstallmentUpdate,
    LoanSummary,
)
from app.services import loan_service

router = APIRouter(prefix="/api/loans", tags=["loans"])


@router.get("", response_model=list[LoanSummary])
async def list_loans(
    include_archived: bool = False,
    ctx: WorkspaceContext = Depends(current_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    return await loan_service.list_loans(session, ctx.workspace.id, include_archived)


@router.post("", response_model=LoanSummary, status_code=status.HTTP_201_CREATED)
async def create_loan(
    data: LoanDetailsCreate,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    return await loan_service.create_loan(session, ctx.workspace.id, ctx.user_id, data)


@router.post("/import", response_model=LoanImportResult)
async def import_loans(
    file: UploadFile = File(...),
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    content = (await file.read()).decode("utf-8-sig")
    return await loan_service.import_loans_csv(session, ctx.workspace.id, ctx.user_id, content)


@router.get("/{loan_id}", response_model=LoanSummary)
async def get_loan(
    loan_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(current_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    summary = await loan_service.get_loan_summary(session, loan_id, ctx.workspace.id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return summary


@router.put("/{loan_id}", response_model=LoanSummary)
async def update_loan(
    loan_id: uuid.UUID,
    data: LoanDetailsCreate,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    summary = await loan_service.update_loan(session, ctx.workspace.id, loan_id, data)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return summary


@router.delete("/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_loan(
    loan_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    deleted = await loan_service.delete_loan(session, loan_id, ctx.workspace.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")


@router.get("/{loan_id}/installments", response_model=list[LoanInstallmentRead])
async def list_installments(
    loan_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(current_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    return await loan_service.list_installments(session, loan_id, ctx.workspace.id)


@router.patch("/{loan_id}/installments/{installment_id}", response_model=LoanInstallmentRead)
async def update_installment(
    loan_id: uuid.UUID,
    installment_id: uuid.UUID,
    data: LoanInstallmentUpdate,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    installment = await loan_service.update_installment(
        session, loan_id, installment_id, ctx.workspace.id, data.status, data.paid_date
    )
    if not installment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installment not found")
    return installment
