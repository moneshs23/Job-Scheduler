import logging
from datetime import datetime, timezone

from croniter import croniter
from sqlalchemy import select

from app.config.constants import JOB_STATUS_QUEUED, JOB_STATUS_SCHEDULED, SCHEDULE_TYPE_DELAY
from app.database.session import AsyncSessionLocal
from app.models.job import Job, ScheduledJob
from app.queues.pubsub import publish_event
from app.queues.redis_client import get_redis
from app.queues.streams import publish_job_ready

logger = logging.getLogger(__name__)


async def scan_delayed_jobs() -> None:
    """Flips one-off delayed/scheduled jobs from 'scheduled' to 'queued' once their run_at has passed."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        stmt = (
            select(ScheduledJob)
            .join(Job, Job.id == ScheduledJob.job_id)
            .where(
                ScheduledJob.schedule_type == SCHEDULE_TYPE_DELAY,
                ScheduledJob.is_active.is_(True),
                ScheduledJob.next_run_at <= now,
                Job.status == JOB_STATUS_SCHEDULED,
            )
        )
        schedules = (await db.execute(stmt)).scalars().all()
        if not schedules:
            return

        redis = get_redis()
        for schedule in schedules:
            job = await db.get(Job, schedule.job_id)
            job.status = JOB_STATUS_QUEUED
            schedule.is_active = False
            schedule.last_run_at = now
            await db.commit()
            await publish_job_ready(redis, job.queue_id, job.id)
            await publish_event(redis, "job.queued", {"job_id": str(job.id), "queue_id": str(job.queue_id)})
        logger.info("Delay scanner promoted %d job(s) to queued", len(schedules))


async def scan_cron_jobs() -> None:
    """Fires recurring/cron job templates whose next_run_at has passed, cloning a fresh Job instance."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        stmt = (
            select(ScheduledJob)
            .join(Job, Job.id == ScheduledJob.job_id)
            .where(
                ScheduledJob.schedule_type.in_(["cron", "recurring"]),
                ScheduledJob.is_active.is_(True),
                ScheduledJob.next_run_at <= now,
            )
        )
        schedules = (await db.execute(stmt)).scalars().all()
        if not schedules:
            return

        redis = get_redis()
        for schedule in schedules:
            template = await db.get(Job, schedule.job_id)

            clone = Job(
                queue_id=template.queue_id,
                project_id=template.project_id,
                name=template.name,
                status=JOB_STATUS_QUEUED,
                priority=template.priority,
                payload=template.payload,
                max_attempts=template.max_attempts,
            )
            db.add(clone)

            schedule.last_run_at = now
            schedule.next_run_at = croniter(schedule.cron_expression, now).get_next(datetime)
            await db.commit()
            await db.refresh(clone)

            await publish_job_ready(redis, clone.queue_id, clone.id)
            await publish_event(redis, "job.queued", {"job_id": str(clone.id), "queue_id": str(clone.queue_id)})
        logger.info("Cron scanner fired %d job instance(s)", len(schedules))
