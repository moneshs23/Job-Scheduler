import uuid

from sqlalchemy import select

from app.models.organization import Organization, OrganizationMember, Project, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return (await self.db.execute(stmt)).scalar_one_or_none()


class OrganizationRepository(BaseRepository[Organization]):
    model = Organization

    async def get_by_slug(self, slug: str) -> Organization | None:
        stmt = select(Organization).where(Organization.slug == slug)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Organization]:
        stmt = (
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
        )
        return list((await self.db.execute(stmt)).scalars().all())


class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Project]:
        stmt = select(Project).where(Project.organization_id == organization_id)
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_slug(self, organization_id: uuid.UUID, slug: str) -> Project | None:
        stmt = select(Project).where(Project.organization_id == organization_id, Project.slug == slug)
        return (await self.db.execute(stmt)).scalar_one_or_none()
