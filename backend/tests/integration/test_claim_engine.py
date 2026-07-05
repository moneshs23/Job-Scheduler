import asyncio
import uuid

import pytest

from app.config.constants import JOB_STATUS_CLAIMED, JOB_STATUS_QUEUED
from app.models.job import Job
from app.models.worker import Worker
from app.repositories.job import JobRepository
from tests.conftest import TestSessionLocal


@pytest.mark.asyncio
async def test_claim_jobs_marks_rows_claimed_and_assigns_worker(seeded_project, db_session):
    queue = seeded_project["queue"]
    project = seeded_project["project"]
    worker = seeded_project["worker"]

    for i in range(5):
        db_session.add(Job(queue_id=queue.id, project_id=project.id, name=f"job-{i}", status=JOB_STATUS_QUEUED))
    await db_session.commit()

    claimed = await JobRepository(db_session).claim_jobs(queue.id, worker.id, limit=3)

    assert len(claimed) == 3
    assert all(job.status == JOB_STATUS_CLAIMED for job in claimed)
    assert all(job.worker_id == worker.id for job in claimed)

    remaining = await JobRepository(db_session).count_active_in_queue(queue.id)
    assert remaining == 3


@pytest.mark.asyncio
async def test_concurrent_claims_never_double_claim_the_same_job(seeded_project, db_session, make_worker):
    """The core reliability guarantee: two workers racing on the same queue must
    never both walk away with the same job — this is what SKIP LOCKED buys us."""
    queue = seeded_project["queue"]
    project = seeded_project["project"]

    job_count = 20
    for i in range(job_count):
        db_session.add(Job(queue_id=queue.id, project_id=project.id, name=f"race-job-{i}", status=JOB_STATUS_QUEUED))
    await db_session.commit()

    workers = [seeded_project["worker"]] + [await make_worker(project.id) for _ in range(3)]

    async def claim_worker(worker_id: uuid.UUID) -> list[uuid.UUID]:
        async with TestSessionLocal() as session:
            claimed = await JobRepository(session).claim_jobs(queue.id, worker_id, limit=job_count)
            return [job.id for job in claimed]

    results = await asyncio.gather(*(claim_worker(w.id) for w in workers))

    all_claimed = [job_id for batch in results for job_id in batch]
    assert len(all_claimed) == job_count
    assert len(set(all_claimed)) == job_count  # no duplicates across workers
