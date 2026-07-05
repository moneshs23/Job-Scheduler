import uuid
from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import (
    CLAIMABLE_JOB_STATUSES,
    JOB_STATUS_CLAIMED,
    JOB_STATUS_RUNNING,
)
from app.models.job import Job
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    model = Job

    async def claim_jobs(self, queue_id: uuid.UUID, worker_id: uuid.UUID, limit: int) -> list[Job]:
        """Atomically claim up to `limit` ready jobs from a queue.

        Uses SELECT ... FOR UPDATE SKIP LOCKED so concurrent workers polling the
        same queue never see (and therefore never double-claim) the same row.
        Must run inside a transaction that commits promptly to release row locks.
        """
        now = datetime.now(timezone.utc)

        candidate_stmt = (
            select(Job.id)
            .where(
                Job.queue_id == queue_id,
                Job.status.in_(CLAIMABLE_JOB_STATUSES),
                or_(Job.scheduled_at.is_(None), Job.scheduled_at <= now),
                or_(Job.next_retry_at.is_(None), Job.next_retry_at <= now),
            )
            .order_by(Job.priority.desc(), Job.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        candidate_ids = (await self.db.execute(candidate_stmt)).scalars().all()
        if not candidate_ids:
            return []

        claim_stmt = (
            update(Job)
            .where(Job.id.in_(candidate_ids))
            .values(status=JOB_STATUS_CLAIMED, claimed_at=now, worker_id=worker_id)
            .returning(Job)
        )
        result = await self.db.execute(claim_stmt)
        claimed = list(result.scalars().all())
        await self.db.commit()
        return claimed

    async def count_active_in_queue(self, queue_id: uuid.UUID) -> int:
        return await self.count(
            Job.queue_id == queue_id, Job.status.in_([JOB_STATUS_CLAIMED, JOB_STATUS_RUNNING])
        )

    async def list_by_project(
        self,
        project_id: uuid.UUID,
        *,
        queue_id: uuid.UUID | None = None,
        status: str | None = None,
        search: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Job], int]:
        filters = [Job.project_id == project_id]
        if queue_id is not None:
            filters.append(Job.queue_id == queue_id)
        if status is not None:
            filters.append(Job.status == status)
        if search:
            filters.append(Job.name.ilike(f"%{search}%"))

        total = await self.count(*filters)

        sort_column = getattr(Job, sort_by, Job.created_at)
        order = sort_column.desc() if sort_order == "desc" else sort_column.asc()

        stmt = select(Job).where(*filters).order_by(order).offset(offset).limit(limit)
        rows = (await self.db.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_by_idempotency_key(self, project_id: uuid.UUID, key: str) -> Job | None:
        stmt = select(Job).where(Job.project_id == project_id, Job.idempotency_key == key)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def stale_claimed(self, cutoff: datetime) -> list[Job]:
        """Jobs claimed/running whose worker has stopped heartbeating — for requeue sweeps."""
        stmt = select(Job).where(
            Job.status.in_([JOB_STATUS_CLAIMED, JOB_STATUS_RUNNING]),
            Job.claimed_at < cutoff,
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def counts_by_status(self, project_id: uuid.UUID) -> dict[str, int]:
        stmt = (
            select(Job.status, func.count())
            .where(Job.project_id == project_id)
            .group_by(Job.status)
        )
        rows = (await self.db.execute(stmt)).all()
        return {status: count for status, count in rows}

    async def counts_by_status_for_queue(self, queue_id: uuid.UUID) -> dict[str, int]:
        stmt = select(Job.status, func.count()).where(Job.queue_id == queue_id).group_by(Job.status)
        rows = (await self.db.execute(stmt)).all()
        return {status: count for status, count in rows}
