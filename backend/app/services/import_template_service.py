import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_template import ImportTemplate
from app.schemas.import_template import ImportTemplateCreate, ImportTemplateUpdate


async def list_templates(
    session: AsyncSession, workspace_id: uuid.UUID, account_id: Optional[uuid.UUID] = None
) -> list[ImportTemplate]:
    query = select(ImportTemplate).where(ImportTemplate.workspace_id == workspace_id)
    if account_id is not None:
        query = query.where(ImportTemplate.account_id == account_id)
    result = await session.execute(query.order_by(ImportTemplate.name))
    return list(result.scalars().all())


async def get_template(
    session: AsyncSession, template_id: uuid.UUID, workspace_id: uuid.UUID
) -> Optional[ImportTemplate]:
    result = await session.execute(
        select(ImportTemplate).where(
            ImportTemplate.id == template_id, ImportTemplate.workspace_id == workspace_id
        )
    )
    return result.scalar_one_or_none()


async def create_template(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: ImportTemplateCreate,
) -> ImportTemplate:
    template = ImportTemplate(user_id=user_id, workspace_id=workspace_id, **data.model_dump())
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def update_template(
    session: AsyncSession,
    template_id: uuid.UUID,
    workspace_id: uuid.UUID,
    data: ImportTemplateUpdate,
) -> Optional[ImportTemplate]:
    template = await get_template(session, template_id, workspace_id)
    if not template:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    await session.commit()
    await session.refresh(template)
    return template


async def delete_template(session: AsyncSession, template_id: uuid.UUID, workspace_id: uuid.UUID) -> bool:
    template = await get_template(session, template_id, workspace_id)
    if not template:
        return False
    await session.delete(template)
    await session.commit()
    return True
