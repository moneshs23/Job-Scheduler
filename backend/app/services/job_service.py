import uuid
from datetime import datetime, timedelta, timezone

from croniter import croniter
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import (
    JOB_STATUS_QUEUED,
    JOB_STATUS_SCHEDULED,
    SCHEDULE_TYPE_CRON,
    SCHEDULE_TYPE_DELAY,
    TERMINAL_JOB_STATUSES,
)
from app.models.job import Job, ScheduledJob
from app.repositories.dead_letter import DeadLetterRepository
from app.repositories.job import JobRepository
from app.repositories.queue import QueueRepository
from app.schemas.job import BatchJobCreate, JobCreate


class JobService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.jobs = JobRepository(db)
        self.queues = QueueRepository(db)
        self.dead_letters = DeadLetterRepository(db)

    async def _resolve_queue(self, project_id: uuid.UUID, queue_id: uuid.UUID):
        queue = await self.queues.get(queue_id)
        if queue is None or queue.project_id != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Queue not found in this project")
        return queue

    async def create_job(self, project_id: uuid.UUID, payload: JobCreate, batch_id: uuid.UUID | None = None) -> Job:
        await self._resolve_queue(project_id, payload.queue_id)

        if payload.idempotency_key:
            existing = await self.jobs.get_by_idempotency_key(project_id, payload.idempotency_key)
            if existing is not None:
                return existing

        now = datetime.now(timezone.utc)
        status_value = JOB_STATUS_QUEUED
        scheduled_at = None
        schedule: ScheduledJob | None = None

        if payload.cron_expression:
            if not croniter.is_valid(payload.cron_expression):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid cron expression")
            status_value = JOB_STATUS_SCHEDULED
            next_run = croniter(payload.cron_expression, now).get_next(datetime)
            schedule = ScheduledJob(
                schedule_type=SCHEDULE_TYPE_CRON,
                cron_expression=payload.cron_expression,
                next_run_at=next_run,
                is_active=True,
            )
        elif payload.delay_seconds is not None:
            scheduled_at = now + timedelta(seconds=payload.delay_seconds)
            status_value = JOB_STATUS_SCHEDULED
            schedule = ScheduledJob(
                schedule_type=SCHEDULE_TYPE_DELAY, run_at=scheduled_at, next_run_at=scheduled_at, is_active=True
            )
        elif payload.run_at is not None:
            scheduled_at = payload.run_at
            status_value = JOB_STATUS_SCHEDULED
            schedule = ScheduledJob(
                schedule_type=SCHEDULE_TYPE_DELAY, run_at=scheduled_at, next_run_at=scheduled_at, is_active=True
            )

        job = Job(
            queue_id=payload.queue_id,
            project_id=project_id,
            name=payload.name,
            status=status_value,
            priority=payload.priority,
            payload=payload.payload,
            idempotency_key=payload.idempotency_key,
            max_attempts=payload.max_attempts,
            scheduled_at=scheduled_at,
            batch_id=batch_id,
        )
        if schedule is not None:
            job.schedule = schedule

        job = await self.jobs.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def create_batch(self, project_id: uuid.UUID, payload: BatchJobCreate) -> list[Job]:
        batch_id = uuid.uuid4()
        created = []
        for item in payload.jobs:
            item = item.model_copy(update={"queue_id": payload.queue_id})
            created.append(await self.create_job(project_id, item, batch_id=batch_id))
        return created

    async def list_jobs(self, project_id: uuid.UUID, **kwargs) -> tuple[list[Job], int]:
        return await self.jobs.list_by_project(project_id, **kwargs)

    async def get_job(self, project_id: uuid.UUID, job_id: uuid.UUID) -> Job:
        job = await self.jobs.get(job_id)
        if job is None or job.project_id != project_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
        return job

    async def cancel_job(self, project_id: uuid.UUID, job_id: uuid.UUID) -> Job:
        job = await self.get_job(project_id, job_id)
        if job.status in TERMINAL_JOB_STATUSES:
            raise HTTPException(status.HTTP_409_CONFLICT, f"Job already in terminal state '{job.status}'")
        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def replay_from_dead_letter(self, project_id: uuid.UUID, job_id: uuid.UUID) -> Job:
        job = await self.get_job(project_id, job_id)
        entry = await self.dead_letters.get_by_job(job_id)
        if entry is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Job is not in the dead letter queue")

        job.status = JOB_STATUS_QUEUED
        job.attempt_count = 0
        job.next_retry_at = None
        job.last_error = None
        job.worker_id = None
        entry.replayed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)
        return job
