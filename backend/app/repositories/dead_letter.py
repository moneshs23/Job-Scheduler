import uuid

from sqlalchemy import select

from app.models.dead_letter import DeadLetterEntry
from app.repositories.base import BaseRepository


class DeadLetterRepository(BaseRepository[DeadLetterEntry]):
    model = DeadLetterEntry

    async def list_for_queue(self, queue_id: uuid.UUID, offset: int = 0, limit: int = 20) -> tuple[list[DeadLetterEntry], int]:
        total = await self.count(DeadLetterEntry.queue_id == queue_id)
        stmt = (
            select(DeadLetterEntry)
            .where(DeadLetterEntry.queue_id == queue_id)
            .order_by(DeadLetterEntry.moved_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_by_job(self, job_id: uuid.UUID) -> DeadLetterEntry | None:
        stmt = select(DeadLetterEntry).where(DeadLetterEntry.job_id == job_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()
