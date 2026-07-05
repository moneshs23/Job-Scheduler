import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_DEAD_LETTER,
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RETRY,
    JOB_STATUS_RUNNING,
    JOB_STATUS_SCHEDULED,
)
from app.models.execution import JobExecution
from app.models.queue import Queue, RetryPolicy
from app.models.worker import Worker
from app.repositories.job import JobRepository
from app.repositories.queue import QueueRepository, RetryPolicyRepository
from app.schemas.queue import QueueMetrics


class QueueService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.queues = QueueRepository(db)
        self.retry_policies = RetryPolicyRepository(db)
        self.jobs = JobRepository(db)

    async def create(
        self,
        project_id: uuid.UUID,
        name: str,
        priority: int,
        concurrency_limit: int,
        retry_policy_id: uuid.UUID | None,
        config: dict | None,
    ) -> Queue:
        if await self.queues.get_by_name(project_id, name):
            raise HTTPException(status.HTTP_409_CONFLICT, "A queue with this name already exists")
        queue = Queue(
            project_id=project_id,
            name=name,
            priority=priority,
            concurrency_limit=concurrency_limit,
            retry_policy_id=retry_policy_id,
            config=config,
        )
        try:
            queue = await self.queues.add(queue)
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "A queue with this name already exists") from exc
        return queue

    async def update(self, queue: Queue, **fields) -> Queue:
        for key, value in fields.items():
            if value is not None:
                setattr(queue, key, value)
        await self.db.commit()
        await self.db.refresh(queue)
        return queue

    async def set_paused(self, queue: Queue, paused: bool) -> Queue:
        queue.is_paused = paused
        await self.db.commit()
        await self.db.refresh(queue)
        return queue

    async def create_retry_policy(self, project_id: uuid.UUID, **fields) -> RetryPolicy:
        policy = await self.retry_policies.add(RetryPolicy(project_id=project_id, **fields))
        await self.db.commit()
        return policy

    async def metrics(self, queue: Queue) -> QueueMetrics:
        counts = await self.jobs.counts_by_status_for_queue(queue.id)

        # Workers aren't queue-scoped in this schema; approximate active worker count
        # as workers in the same project that have heartbeated recently.
        recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
        active_workers_stmt = select(Worker.id).where(
            Worker.project_id == queue.project_id,
            Worker.last_heartbeat_at.is_not(None),
            Worker.last_heartbeat_at >= recent_cutoff,
        )
        active_workers = len((await self.db.execute(active_workers_stmt)).scalars().all())

        window_start = datetime.now(timezone.utc) - timedelta(minutes=1)
        throughput_stmt = select(JobExecution.id).where(
            JobExecution.status == JOB_STATUS_COMPLETED,
            JobExecution.finished_at >= window_start,
            JobExecution.job_id.in_(select(self.jobs.model.id).where(self.jobs.model.queue_id == queue.id)),
        )
        throughput = len((await self.db.execute(throughput_stmt)).scalars().all())

        avg_latency_stmt = select(JobExecution.duration_ms).where(
            JobExecution.status == JOB_STATUS_COMPLETED,
            JobExecution.job_id.in_(select(self.jobs.model.id).where(self.jobs.model.queue_id == queue.id)),
        ).order_by(JobExecution.finished_at.desc()).limit(200)
        durations = [d for d in (await self.db.execute(avg_latency_stmt)).scalars().all() if d is not None]
        avg_latency = sum(durations) / len(durations) if durations else None

        return QueueMetrics(
            queue_id=queue.id,
            queue_name=queue.name,
            queued=counts.get(JOB_STATUS_QUEUED, 0),
            scheduled=counts.get(JOB_STATUS_SCHEDULED, 0),
            running=counts.get(JOB_STATUS_RUNNING, 0),
            completed=counts.get(JOB_STATUS_COMPLETED, 0),
            failed=counts.get(JOB_STATUS_FAILED, 0),
            retry=counts.get(JOB_STATUS_RETRY, 0),
            dead_letter=counts.get(JOB_STATUS_DEAD_LETTER, 0),
            is_paused=queue.is_paused,
            concurrency_limit=queue.concurrency_limit,
            active_workers=active_workers,
            throughput_per_min=float(throughput),
            avg_latency_ms=avg_latency,
        )
