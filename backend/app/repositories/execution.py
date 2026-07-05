import uuid

from sqlalchemy import select

from app.models.execution import JobExecution, JobLog
from app.repositories.base import BaseRepository


class JobExecutionRepository(BaseRepository[JobExecution]):
    model = JobExecution

    async def list_for_job(self, job_id: uuid.UUID) -> list[JobExecution]:
        stmt = (
            select(JobExecution)
            .where(JobExecution.job_id == job_id)
            .order_by(JobExecution.attempt_number.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())


class JobLogRepository(BaseRepository[JobLog]):
    model = JobLog

    async def list_for_job(self, job_id: uuid.UUID, limit: int = 500) -> list[JobLog]:
        stmt = (
            select(JobLog)
            .where(JobLog.job_id == job_id)
            .order_by(JobLog.logged_at.asc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())
