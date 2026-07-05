import uuid

from sqlalchemy import select

from app.models.api_key import APIKey
from app.models.audit import AuditLog
from app.repositories.base import BaseRepository


class APIKeyRepository(BaseRepository[APIKey]):
    model = APIKey

    async def list_for_user(self, user_id: uuid.UUID) -> list[APIKey]:
        stmt = select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_hash(self, key_hash: str) -> APIKey | None:
        stmt = select(APIKey).where(APIKey.key_hash == key_hash)
        return (await self.db.execute(stmt)).scalar_one_or_none()


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def list_for_organization(
        self, organization_id: uuid.UUID, offset: int = 0, limit: int = 50
    ) -> tuple[list[AuditLog], int]:
        total = await self.count(AuditLog.organization_id == organization_id)
        stmt = (
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return list(rows), total
