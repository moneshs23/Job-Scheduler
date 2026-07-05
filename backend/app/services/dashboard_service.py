import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_DEAD_LETTER,
    JOB_STATUS_FAILED,
    JOB_STATUS_QUEUED,
    JOB_STATUS_RUNNING,
)
from app.models.execution import JobExecution
from app.models.job import Job
from app.models.queue import Queue
from app.models.worker import Worker
from app.repositories.job import JobRepository
from app.schemas.dashboard import OverviewStats


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.jobs = JobRepository(db)

    async def overview(self, project_id: uuid.UUID) -> OverviewStats:
        counts = await self.jobs.counts_by_status(project_id)
        total_jobs = sum(counts.values())

        recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=30)
        workers_stmt = select(Worker.status).where(Worker.project_id == project_id)
        worker_statuses = (await self.db.execute(workers_stmt)).scalars().all()
        active_workers_stmt = select(Worker.id).where(
            Worker.project_id == project_id,
            Worker.last_heartbeat_at.is_not(None),
            Worker.last_heartbeat_at >= recent_cutoff,
        )
        active_workers = len((await self.db.execute(active_workers_stmt)).scalars().all())

        queues_stmt = select(Queue.is_paused).where(Queue.project_id == project_id)
        queue_paused_flags = (await self.db.execute(queues_stmt)).scalars().all()

        window_start = datetime.now(timezone.utc) - timedelta(minutes=1)
        throughput_stmt = select(JobExecution.id).join(Job, JobExecution.job_id == Job.id).where(
            Job.project_id == project_id,
            JobExecution.status == JOB_STATUS_COMPLETED,
            JobExecution.finished_at >= window_start,
        )
        throughput = len((await self.db.execute(throughput_stmt)).scalars().all())

        completed = counts.get(JOB_STATUS_COMPLETED, 0)
        failed = counts.get(JOB_STATUS_FAILED, 0)
        finished = completed + failed
        failure_rate = (failed / finished * 100) if finished else 0.0

        return OverviewStats(
            total_jobs=total_jobs,
            queued_jobs=counts.get(JOB_STATUS_QUEUED, 0),
            running_jobs=counts.get(JOB_STATUS_RUNNING, 0),
            completed_jobs=completed,
            failed_jobs=failed,
            dead_letter_jobs=counts.get(JOB_STATUS_DEAD_LETTER, 0),
            active_workers=active_workers,
            total_workers=len(worker_statuses),
            active_queues=len([p for p in queue_paused_flags if not p]),
            paused_queues=len([p for p in queue_paused_flags if p]),
            throughput_per_min=float(throughput),
            failure_rate_pct=round(failure_rate, 2),
        )
