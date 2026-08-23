import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.category_group import CategoryGroup
from app.schemas.category import (
    CategoryCreate,
    CategoryExportItem,
    CategoryExportPayload,
    CategoryGroupExportItem,
    CategoryImportResponse,
    CategoryUpdate,
)
from app.services.category_group_service import CATEGORY_TO_GROUP, create_default_groups


# Language-keyed translations for default categories
# Keys are internal identifiers used to map to groups and rules.
# `treat_as_transfer` marks categories whose transactions are flows, not
# income/expense — they're excluded from report aggregations like paired
# transfers are.
DEFAULT_CATEGORIES_I18N = {
    "housing":       {"en": "Housing",       "pt-BR": "Moradia",        "pt-PT": "Habitação",             "de": "Wohnen",            "fr": "Logement",             "icon": "house",            "color": "#8B5CF6"},
    "food":          {"en": "Food & Dining", "pt-BR": "Alimentação",    "pt-PT": "Alimentação",           "de": "Essen & Trinken",   "fr": "Alimentation & Restaurants", "icon": "utensils-crossed", "color": "#F59E0B"},
    "transport":     {"en": "Transport",     "pt-BR": "Transporte",     "pt-PT": "Transportes",           "de": "Transport",         "fr": "Transport",            "icon": "car",              "color": "#3B82F6"},
    "groceries":     {"en": "Groceries",     "pt-BR": "Mercado",        "pt-PT": "Supermercado",          "de": "Lebensmittel",      "fr": "Courses",              "icon": "shopping-cart",    "color": "#10B981"},
    "health":        {"en": "Health",        "pt-BR": "Saúde",          "pt-PT": "Saúde",                 "de": "Gesundheit",        "fr": "Santé",                "icon": "pill",             "color": "#EF4444"},
    "leisure":       {"en": "Leisure",       "pt-BR": "Lazer",          "pt-PT": "Lazer",                 "de": "Freizeit",          "fr": "Loisirs",              "icon": "gamepad-2",        "color": "#EC4899"},
    "subscriptions": {"en": "Subscriptions", "pt-BR": "Assinaturas",    "pt-PT": "Subscrições",           "de": "Abonnements",       "fr": "Abonnements",          "icon": "smartphone",       "color": "#6366F1"},
    "education":     {"en": "Education",     "pt-BR": "Educação",       "pt-PT": "Educação",              "de": "Bildung",           "fr": "Éducation",            "icon": "book-open",        "color": "#22C55E"},
    "transfers":     {"en": "Transfers",     "pt-BR": "Transferências", "pt-PT": "Transferências",        "de": "Umbuchungen",       "fr": "Virements",            "icon": "arrow-left-right", "color": "#64748B", "treat_as_transfer": True},
    "investments":   {"en": "Investments",   "pt-BR": "Investimentos",  "pt-PT": "Investimentos",         "de": "Investitionen",     "fr": "Investissements",      "icon": "trending-up",      "color": "#0EA5E9", "treat_as_transfer": True},
    "salary":        {"en": "Salary & Income",  "pt-BR": "Salário & Renda",     "pt-PT": "Salário & Rendimentos", "de": "Gehalt & Einnahmen", "fr": "Salaire & Revenus",  "icon": "banknote",         "color": "#16A34A"},
    "shopping":      {"en": "Shopping",         "pt-BR": "Compras",             "pt-PT": "Compras",               "de": "Shopping",           "fr": "Achats",             "icon": "shopping-bag",     "color": "#F97316"},
    "donations":     {"en": "Donations",        "pt-BR": "Doações",             "pt-PT": "Donativos",             "de": "Spenden",            "fr": "Dons",               "icon": "heart-handshake",  "color": "#D946EF"},
    "personal_care": {"en": "Personal Care",    "pt-BR": "Cuidados Pessoais",   "pt-PT": "Cuidados Pessoais",     "de": "Körperpflege",       "fr": "Soins personnels",   "icon": "scissors",         "color": "#F472B6"},
    "taxes":         {"en": "Taxes & Fees",     "pt-BR": "Impostos & Taxas",    "pt-PT": "Impostos & Taxas",      "de": "Steuern & Gebühren", "fr": "Impôts & Taxes",     "icon": "landmark",         "color": "#78716C"},
    "other":         {"en": "Other",         "pt-BR": "Outros",         "pt-PT": "Outros",                "de": "Sonstiges",          "fr": "Autres",               "icon": "circle-help",      "color": "#6B7280"},
}


async def create_default_categories(
    session: AsyncSession,
    user_id: uuid.UUID,
    lang: str = "pt-BR",
    workspace_id: Optional[uuid.UUID] = None,
) -> list[Category]:
    # Guard against double-creation. Scope the check to the workspace
    # when one is provided so a user creating a SECOND workspace still
    # gets the defaults seeded there — the prior guard checked
    # user_id and short-circuited every workspace after the first.
    if workspace_id is not None:
        existing = await session.execute(
            select(Category).where(Category.workspace_id == workspace_id).limit(1)
        )
        if existing.scalar_one_or_none():
            return await get_categories(session, workspace_id)
    else:
        # Legacy/test path with no explicit workspace_id — fall back to
        # the user's first workspace via the autostamp listener.
        existing = await session.execute(
            select(Category).where(Category.user_id == user_id).limit(1)
        )
        if existing.scalar_one_or_none():
            from app.models.workspace import Workspace, WorkspaceMember
            row = await session.execute(
                select(Workspace.id)
                .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
                .where(WorkspaceMember.user_id == user_id)
                .limit(1)
            )
            scope_id = row.scalar()
            return await get_categories(session, scope_id) if scope_id else []

    # Create default groups first
    groups = await create_default_groups(session, user_id, lang, workspace_id=workspace_id)

    categories = []
    for key, data in DEFAULT_CATEGORIES_I18N.items():
        name = data.get(lang, data.get("en", key))
        group_key = CATEGORY_TO_GROUP.get(key)
        group = groups.get(group_key) if group_key else None
        category = Category(
            user_id=user_id,
            workspace_id=workspace_id,
            name=name,
            icon=data["icon"],
            color=data["color"],
            is_system=True,
            group_id=group.id if group else None,
            treat_as_transfer=data.get("treat_as_transfer", False),
        )
        session.add(category)
        categories.append(category)
    await session.commit()
    return categories


async def get_categories(session: AsyncSession, workspace_id: uuid.UUID) -> list[Category]:
    result = await session.execute(
        select(Category)
        .where(Category.workspace_id == workspace_id)
        .order_by(Category.is_system.desc(), Category.name)
    )
    return list(result.scalars().all())


async def get_category(
    session: AsyncSession, category_id: uuid.UUID, workspace_id: uuid.UUID
) -> Optional[Category]:
    result = await session.execute(
        select(Category).where(
            Category.id == category_id, Category.workspace_id == workspace_id
        )
    )
    return result.scalar_one_or_none()


async def create_category(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: CategoryCreate,
) -> Category:
    category = Category(user_id=user_id, workspace_id=workspace_id, **data.model_dump())
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


async def update_category(
    session: AsyncSession,
    category_id: uuid.UUID,
    workspace_id: uuid.UUID,
    data: CategoryUpdate,
) -> Optional[Category]:
    category = await get_category(session, category_id, workspace_id)
    if not category:
        return None

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(category, key, value)

    await session.commit()
    await session.refresh(category)
    return category


async def delete_category(
    session: AsyncSession, category_id: uuid.UUID, workspace_id: uuid.UUID
) -> bool:
    # `is_system` categories are deletable too — the default set is a starting
    # point, not a fixed inventory. Transactions/recurring rows referencing this
    # category fall back to uncategorized (FK ON DELETE SET NULL); budgets that
    # require it are removed along with it (FK ON DELETE CASCADE).
    category = await get_category(session, category_id, workspace_id)
    if not category:
        return False

    await session.delete(category)
    await session.commit()
    return True


async def export_categories(session: AsyncSession, workspace_id: uuid.UUID) -> CategoryExportPayload:
    """Return a portable JSON export of categories/groups for a workspace.

    Groups and categories are serialized by name rather than UUID (same
    convention as rule_service.export_rules) so the file can be imported into
    another instance/workspace with different database IDs.
    """
    groups_result = await session.execute(
        select(CategoryGroup).where(CategoryGroup.workspace_id == workspace_id).order_by(CategoryGroup.position)
    )
    groups = list(groups_result.scalars().all())
    group_names = {str(g.id): g.name for g in groups}

    categories = await get_categories(session, workspace_id)

    return CategoryExportPayload(
        groups=[
            CategoryGroupExportItem(name=g.name, icon=g.icon, color=g.color, position=g.position)
            for g in groups
        ],
        categories=[
            CategoryExportItem(
                name=c.name,
                icon=c.icon,
                color=c.color,
                group_name=group_names.get(str(c.group_id)) if c.group_id else None,
                treat_as_transfer=c.treat_as_transfer,
                is_ignored=c.is_ignored,
            )
            for c in categories
        ],
    )


async def import_categories(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: CategoryExportPayload,
    overwrite: bool = False,
) -> CategoryImportResponse:
    """Import a portable categories/groups payload into a workspace.

    Groups and categories are matched by name (find-or-create). Existing
    categories are only updated when the caller explicitly passes
    `overwrite=True`; otherwise they're skipped.
    """
    existing_groups_result = await session.execute(
        select(CategoryGroup).where(CategoryGroup.workspace_id == workspace_id)
    )
    groups_by_name = {g.name: g for g in existing_groups_result.scalars().all()}

    groups_created = 0
    for group_item in payload.groups:
        existing_group = groups_by_name.get(group_item.name)
        if existing_group:
            if overwrite:
                existing_group.icon = group_item.icon
                existing_group.color = group_item.color
                existing_group.position = group_item.position
            continue
        new_group = CategoryGroup(
            user_id=user_id,
            workspace_id=workspace_id,
            name=group_item.name,
            icon=group_item.icon,
            color=group_item.color,
            position=group_item.position,
            is_system=False,
        )
        session.add(new_group)
        await session.flush()
        groups_by_name[new_group.name] = new_group
        groups_created += 1

    existing_categories_result = await session.execute(
        select(Category).where(Category.workspace_id == workspace_id)
    )
    categories_by_name = {c.name: c for c in existing_categories_result.scalars().all()}

    categories_imported = 0
    categories_updated = 0
    categories_skipped = 0
    for cat_item in payload.categories:
        group = groups_by_name.get(cat_item.group_name) if cat_item.group_name else None
        existing_category = categories_by_name.get(cat_item.name)
        if existing_category:
            if overwrite:
                existing_category.icon = cat_item.icon
                existing_category.color = cat_item.color
                existing_category.group_id = group.id if group else None
                existing_category.treat_as_transfer = cat_item.treat_as_transfer
                existing_category.is_ignored = cat_item.is_ignored
                categories_updated += 1
            else:
                categories_skipped += 1
            continue
        new_category = Category(
            user_id=user_id,
            workspace_id=workspace_id,
            name=cat_item.name,
            icon=cat_item.icon,
            color=cat_item.color,
            group_id=group.id if group else None,
            is_system=False,
            treat_as_transfer=cat_item.treat_as_transfer,
            is_ignored=cat_item.is_ignored,
        )
        session.add(new_category)
        categories_by_name[new_category.name] = new_category
        categories_imported += 1

    await session.commit()
    return CategoryImportResponse(
        groups_created=groups_created,
        categories_imported=categories_imported,
        categories_updated=categories_updated,
        categories_skipped=categories_skipped,
    )
