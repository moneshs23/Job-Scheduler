import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Project
from app.repositories.organization import OrganizationRepository, ProjectRepository
from app.services.auth_service import slugify


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.projects = ProjectRepository(db)
        self.orgs = OrganizationRepository(db)

    async def create(
        self, organization_id: uuid.UUID, name: str, description: str | None, settings: dict | None
    ) -> Project:
        if await self.orgs.get(organization_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")

        base_slug = slugify(name)
        slug = base_slug
        suffix = 1
        while await self.projects.get_by_slug(organization_id, slug):
            suffix += 1
            slug = f"{base_slug}-{suffix}"

        project = await self.projects.add(
            Project(
                organization_id=organization_id,
                name=name,
                slug=slug,
                description=description,
                settings=settings,
            )
        )
        await self.db.commit()
        return project

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Project]:
        return await self.projects.list_for_organization(organization_id)

    async def update(
        self, project: Project, name: str | None, description: str | None, settings: dict | None
    ) -> Project:
        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        if settings is not None:
            project.settings = settings
        await self.db.commit()
        await self.db.refresh(project)
        return project
