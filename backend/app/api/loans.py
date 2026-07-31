import uuid
from datetime import date

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
    LoanDetailsRead,
    LoanImportResult,
    LoanInstallmentRead,
    LoanInstallmentUpdate,
    LoanSummary,
)
from app.services import loan_service

router = APIRouter(tags=["loans"])


@router.post("/api/loans/import", response_model=LoanImportResult)
async def import_loans(
    file: UploadFile = File(...),
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    content = (await file.read()).decode("utf-8-sig")
    return await loan_service.import_loans_csv(session, ctx.workspace.id, ctx.user_id, content)


@router.get("/api/accounts/{account_id}/loan", response_model=LoanSummary)
async def get_loan(
    account_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(current_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    summary = await loan_service.get_loan_summary(session, account_id, ctx.workspace.id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return summary


@router.put("/api/accounts/{account_id}/loan", response_model=LoanDetailsRead)
async def save_loan(
    account_id: uuid.UUID,
    data: LoanDetailsCreate,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    return await loan_service.create_or_replace_loan(session, ctx.workspace.id, ctx.user_id, account_id, data)


@router.get("/api/accounts/{account_id}/loan/installments", response_model=list[LoanInstallmentRead])
async def list_installments(
    account_id: uuid.UUID,
    ctx: WorkspaceContext = Depends(current_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    return await loan_service.list_installments(session, account_id, ctx.workspace.id)


@router.patch("/api/accounts/{account_id}/loan/installments/{installment_id}", response_model=LoanInstallmentRead)
async def update_installment(
    account_id: uuid.UUID,
    installment_id: uuid.UUID,
    data: LoanInstallmentUpdate,
    ctx: WorkspaceContext = Depends(current_writable_workspace),
    session: AsyncSession = Depends(get_async_session),
):
    installment = await loan_service.update_installment(
        session, account_id, installment_id, ctx.workspace.id, data.status, data.paid_date
    )
    if not installment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Installment not found")
    return installment
