import time
import traceback
import uuid
from datetime import datetime, timezone

from app.config.constants import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_DEAD_LETTER,
    JOB_STATUS_FAILED,
    JOB_STATUS_RETRY,
    JOB_STATUS_RUNNING,
)
from app.database.session import AsyncSessionLocal
from app.execution.registry import get_task
from app.models.dead_letter import DeadLetterEntry
from app.models.execution import JobExecution, JobLog
from app.monitoring.metrics import (
    JOBS_COMPLETED_TOTAL,
    JOBS_DEAD_LETTERED_TOTAL,
    JOBS_FAILED_TOTAL,
    JOB_EXECUTION_DURATION_SECONDS,
)
from app.queues.pubsub import publish_event
from app.queues.redis_client import get_redis
from app.repositories.dead_letter import DeadLetterRepository
from app.repositories.execution import JobExecutionRepository, JobLogRepository
from app.repositories.job import JobRepository
from app.repositories.queue import QueueRepository, RetryPolicyRepository
from app.retry.policy import next_retry_at


async def execute_job(job_id: uuid.UUID, worker_id: uuid.UUID) -> None:
    """Runs one claimed job to completion (success, retry, or dead-letter).

    Owns its own session/transaction so long-running jobs don't hold a
    connection tied to unrelated request or polling work.
    """
    redis = get_redis()

    async with AsyncSessionLocal() as db:
        jobs = JobRepository(db)
        executions = JobExecutionRepository(db)
        logs = JobLogRepository(db)
        queues = QueueRepository(db)
        dead_letters = DeadLetterRepository(db)

        job = await jobs.get(job_id)
        if job is None:
            return

        queue = await queues.get(job.queue_id)
        retry_policy = None
        if queue is not None and queue.retry_policy_id is not None:
            retry_policy = await RetryPolicyRepository(db).get(queue.retry_policy_id)

        attempt_number = job.attempt_count + 1
        job.status = JOB_STATUS_RUNNING
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        await publish_event(
            redis, "job.started", {"job_id": str(job.id), "queue_id": str(job.queue_id), "attempt": attempt_number}
        )

        execution = await executions.add(
            JobExecution(
                job_id=job.id,
                worker_id=worker_id,
                attempt_number=attempt_number,
                status=JOB_STATUS_RUNNING,
                started_at=job.started_at,
            )
        )
        await db.commit()

        handler = get_task((job.payload or {}).get("task", "echo"))
        started = time.monotonic()
        result: dict | None = None
        error_message: str | None = None
        error_stack: str | None = None

        try:
            if handler is None:
                raise RuntimeError(f"No task handler registered for '{(job.payload or {}).get('task')}'")
            result = await handler((job.payload or {}).get("args", {}))
            succeeded = True
        except Exception as exc:  # noqa: BLE001 - job failures must never crash the worker
            succeeded = False
            error_message = str(exc)
            error_stack = traceback.format_exc()

        duration_ms = int((time.monotonic() - started) * 1000)
        finished_at = datetime.now(timezone.utc)
        JOB_EXECUTION_DURATION_SECONDS.labels(queue_id=str(job.queue_id)).observe(duration_ms / 1000)

        execution.status = JOB_STATUS_COMPLETED if succeeded else JOB_STATUS_FAILED
        execution.finished_at = finished_at
        execution.duration_ms = duration_ms
        execution.result = result
        execution.error_message = error_message
        execution.error_stack = error_stack

        await logs.add(
            JobLog(
                job_id=job.id,
                execution_id=execution.id,
                level="info" if succeeded else "error",
                message="Job completed successfully" if succeeded else f"Job failed: {error_message}",
                context={"attempt": attempt_number, "duration_ms": duration_ms},
            )
        )

        job.attempt_count = attempt_number
        job.worker_id = worker_id

        if succeeded:
            job.status = JOB_STATUS_COMPLETED
            job.completed_at = finished_at
            job.last_error = None
            await db.commit()
            JOBS_COMPLETED_TOTAL.labels(queue_id=str(job.queue_id)).inc()
            await publish_event(
                redis, "job.completed", {"job_id": str(job.id), "queue_id": str(job.queue_id), "duration_ms": duration_ms}
            )
            return

        job.last_error = error_message
        max_attempts = job.max_attempts

        if attempt_number < max_attempts:
            job.status = JOB_STATUS_RETRY
            job.next_retry_at = next_retry_at(retry_policy, attempt_number)
            await db.commit()
            JOBS_FAILED_TOTAL.labels(queue_id=str(job.queue_id)).inc()
            await publish_event(
                redis,
                "job.retry",
                {
                    "job_id": str(job.id),
                    "queue_id": str(job.queue_id),
                    "attempt": attempt_number,
                    "next_retry_at": job.next_retry_at.isoformat(),
                },
            )
        else:
            job.status = JOB_STATUS_DEAD_LETTER
            job.completed_at = finished_at
            await dead_letters.add(
                DeadLetterEntry(
                    job_id=job.id,
                    queue_id=job.queue_id,
                    original_payload=job.payload,
                    failure_reason=error_message,
                    total_attempts=attempt_number,
                )
            )
            await db.commit()
            JOBS_DEAD_LETTERED_TOTAL.labels(queue_id=str(job.queue_id)).inc()
            await publish_event(
                redis,
                "job.dead_letter",
                {"job_id": str(job.id), "queue_id": str(job.queue_id), "reason": error_message},
            )
