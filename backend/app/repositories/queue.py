import uuid

from sqlalchemy import select

from app.models.queue import Queue, RetryPolicy
from app.repositories.base import BaseRepository


class RetryPolicyRepository(BaseRepository[RetryPolicy]):
    model = RetryPolicy

    async def list_for_project(self, project_id: uuid.UUID) -> list[RetryPolicy]:
        stmt = select(RetryPolicy).where(RetryPolicy.project_id == project_id)
        return list((await self.db.execute(stmt)).scalars().all())


class QueueRepository(BaseRepository[Queue]):
    model = Queue

    async def list_for_project(self, project_id: uuid.UUID) -> list[Queue]:
        stmt = select(Queue).where(Queue.project_id == project_id).order_by(Queue.priority.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_active_for_project(self, project_id: uuid.UUID) -> list[Queue]:
        stmt = (
            select(Queue)
            .where(Queue.project_id == project_id, Queue.is_paused.is_(False))
            .order_by(Queue.priority.desc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_by_name(self, project_id: uuid.UUID, name: str) -> Queue | None:
        stmt = select(Queue).where(Queue.project_id == project_id, Queue.name == name)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_all_active(self) -> list[Queue]:
        """Every non-paused queue system-wide — used by worker polling loops."""
        stmt = select(Queue).where(Queue.is_paused.is_(False)).order_by(Queue.priority.desc())
        return list((await self.db.execute(stmt)).scalars().all())
