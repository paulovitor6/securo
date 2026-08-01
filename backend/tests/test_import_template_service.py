from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.schemas.import_template import ImportTemplateCreate, ImportTemplateUpdate
from app.services import import_template_service


@pytest.fixture
async def test_account(session: AsyncSession, test_user, test_workspace) -> Account:
    account = Account(
        user_id=test_user.id, workspace_id=test_workspace.id, name="Nubank",
        type="checking", balance=Decimal("0"), currency="BRL",
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


@pytest.mark.asyncio
async def test_create_and_list_template(session: AsyncSession, test_user, test_workspace, test_account):
    created = await import_template_service.create_template(
        session, test_workspace.id, test_user.id,
        ImportTemplateCreate(
            account_id=test_account.id,
            name="Extrato Nubank",
            column_mapping={"date": "Data", "amount": "Valor"},
            date_format="DD/MM/YYYY",
            delimiter=";",
        ),
    )
    assert created.name == "Extrato Nubank"
    assert created.delimiter == ";"

    templates = await import_template_service.list_templates(session, test_workspace.id, test_account.id)
    assert len(templates) == 1
    assert templates[0].column_mapping == {"date": "Data", "amount": "Valor"}
    assert templates[0].delimiter == ";"


@pytest.mark.asyncio
async def test_update_and_delete_template(session: AsyncSession, test_user, test_workspace, test_account):
    created = await import_template_service.create_template(
        session, test_workspace.id, test_user.id,
        ImportTemplateCreate(account_id=test_account.id, name="Old name", column_mapping={}),
    )
    updated = await import_template_service.update_template(
        session, created.id, test_workspace.id, ImportTemplateUpdate(name="New name"),
    )
    assert updated.name == "New name"

    deleted = await import_template_service.delete_template(session, created.id, test_workspace.id)
    assert deleted is True
    assert await import_template_service.get_template(session, created.id, test_workspace.id) is None
