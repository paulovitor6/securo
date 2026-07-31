from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.asset_group import AssetGroupCreate
from app.services import asset_group_service, asset_service


@pytest.mark.asyncio
async def test_import_snapshot_creates_manual_assets(session: AsyncSession, test_user, test_workspace):
    group = await asset_group_service.create_group(
        session, test_workspace.id, test_user.id, AssetGroupCreate(name="Investimentos"),
    )
    csv_content = (
        "name,type,quantity,value\n"
        "Tesouro Selic 2029,fund,10,15234.50\n"
        "Apple Inc,stock,5,4200.00\n"
    )
    result = await asset_service.import_snapshot(
        session, test_workspace.id, test_user.id, group.id, csv_content, date(2026, 7, 1),
    )
    assert result.created == 2
    assert result.updated == 0
    assert result.values_recorded == 2
    assert result.errors == []


@pytest.mark.asyncio
async def test_import_snapshot_reimport_same_month_updates_not_duplicates(
    session: AsyncSession, test_user, test_workspace
):
    group = await asset_group_service.create_group(
        session, test_workspace.id, test_user.id, AssetGroupCreate(name="Investimentos"),
    )
    csv_july = "name,type,quantity,value\nTesouro Selic 2029,fund,10,15000.00\n"
    await asset_service.import_snapshot(session, test_workspace.id, test_user.id, group.id, csv_july, date(2026, 7, 1))

    # Re-import the same month with an updated value — should update the
    # existing asset + AssetValue, not create a second one.
    csv_july_updated = "name,type,quantity,value\nTesouro Selic 2029,fund,10,15500.00\n"
    result = await asset_service.import_snapshot(
        session, test_workspace.id, test_user.id, group.id, csv_july_updated, date(2026, 7, 1),
    )
    assert result.created == 0
    assert result.updated == 1

    values = await asset_service.get_asset_values(
        session,
        (await asset_service.get_assets(session, test_workspace.id))[0].id,
        test_workspace.id,
    )
    assert len(values) == 1
    assert values[0].amount == 15500.00


@pytest.mark.asyncio
async def test_import_snapshot_reports_row_errors(session: AsyncSession, test_user, test_workspace):
    group = await asset_group_service.create_group(
        session, test_workspace.id, test_user.id, AssetGroupCreate(name="Investimentos"),
    )
    csv_content = "name,type,quantity,value\n,fund,10,15000.00\nApple Inc,stock,5,not-a-number\n"
    result = await asset_service.import_snapshot(
        session, test_workspace.id, test_user.id, group.id, csv_content, date(2026, 7, 1),
    )
    assert result.created == 0
    assert len(result.errors) == 2
