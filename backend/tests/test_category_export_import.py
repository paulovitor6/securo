import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.category import CategoryCreate, CategoryGroupExportItem, CategoryExportItem, CategoryExportPayload
from app.schemas.category_group import CategoryGroupCreate
from app.services import category_group_service, category_service


@pytest.mark.asyncio
async def test_export_categories_round_trip(session: AsyncSession, test_user, test_workspace):
    group = await category_group_service.create_group(
        session, test_workspace.id, test_user.id,
        CategoryGroupCreate(name="Moradia", icon="house", color="#8B5CF6", position=0),
    )
    await category_service.create_category(
        session, test_workspace.id, test_user.id,
        CategoryCreate(name="Aluguel", icon="house", color="#8B5CF6", group_id=group.id, treat_as_transfer=False),
    )

    payload = await category_service.export_categories(session, test_workspace.id)
    assert payload.format == "securo-categories"
    assert any(g.name == "Moradia" for g in payload.groups)
    exported_cat = next(c for c in payload.categories if c.name == "Aluguel")
    assert exported_cat.group_name == "Moradia"


@pytest.mark.asyncio
async def test_import_categories_creates_groups_and_categories(session: AsyncSession, test_user, test_workspace):
    payload = CategoryExportPayload(
        groups=[CategoryGroupExportItem(name="Lazer", icon="gamepad-2", color="#EC4899", position=0)],
        categories=[
            CategoryExportItem(name="Cinema", icon="gamepad-2", color="#EC4899", group_name="Lazer"),
        ],
    )
    result = await category_service.import_categories(session, test_workspace.id, test_user.id, payload)
    assert result.groups_created == 1
    assert result.categories_imported == 1
    assert result.categories_skipped == 0

    categories = await category_service.get_categories(session, test_workspace.id)
    imported = next(c for c in categories if c.name == "Cinema")
    assert imported.is_system is False
    groups = await category_group_service.get_groups(session, test_workspace.id)
    assert any(g.name == "Lazer" for g in groups)


@pytest.mark.asyncio
async def test_import_categories_skips_existing_without_overwrite(session: AsyncSession, test_user, test_workspace):
    await category_service.create_category(
        session, test_workspace.id, test_user.id,
        CategoryCreate(name="Cinema", icon="gamepad-2", color="#000000"),
    )
    payload = CategoryExportPayload(
        groups=[],
        categories=[CategoryExportItem(name="Cinema", icon="gamepad-2", color="#EC4899", group_name=None)],
    )
    result = await category_service.import_categories(session, test_workspace.id, test_user.id, payload, overwrite=False)
    assert result.categories_skipped == 1
    assert result.categories_imported == 0

    categories = await category_service.get_categories(session, test_workspace.id)
    cinema = next(c for c in categories if c.name == "Cinema")
    assert cinema.color == "#000000"  # untouched


@pytest.mark.asyncio
async def test_import_categories_overwrite_updates_existing(session: AsyncSession, test_user, test_workspace):
    await category_service.create_category(
        session, test_workspace.id, test_user.id,
        CategoryCreate(name="Cinema", icon="gamepad-2", color="#000000"),
    )
    payload = CategoryExportPayload(
        groups=[],
        categories=[CategoryExportItem(name="Cinema", icon="gamepad-2", color="#EC4899", group_name=None)],
    )
    result = await category_service.import_categories(session, test_workspace.id, test_user.id, payload, overwrite=True)
    assert result.categories_updated == 1

    categories = await category_service.get_categories(session, test_workspace.id)
    cinema = next(c for c in categories if c.name == "Cinema")
    assert cinema.color == "#EC4899"
