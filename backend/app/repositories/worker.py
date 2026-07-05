import uuid
from datetime import datetime

from sqlalchemy import select

from app.models.worker import Worker, WorkerHeartbeat
from app.repositories.base import BaseRepository


class WorkerRepository(BaseRepository[Worker]):
    model = Worker

    async def list_for_project(self, project_id: uuid.UUID) -> list[Worker]:
        stmt = select(Worker).where(Worker.project_id == project_id).order_by(Worker.registered_at.desc())
        return list((await self.db.execute(stmt)).scalars().all())

    async def stale(self, cutoff: datetime) -> list[Worker]:
        stmt = select(Worker).where(
            Worker.status != "stopped",
            (Worker.last_heartbeat_at.is_(None)) | (Worker.last_heartbeat_at < cutoff),
        )
        return list((await self.db.execute(stmt)).scalars().all())


class WorkerHeartbeatRepository(BaseRepository[WorkerHeartbeat]):
    model = WorkerHeartbeat

    async def recent_for_worker(self, worker_id: uuid.UUID, limit: int = 50) -> list[WorkerHeartbeat]:
        stmt = (
            select(WorkerHeartbeat)
            .where(WorkerHeartbeat.worker_id == worker_id)
            .order_by(WorkerHeartbeat.heartbeat_at.desc())
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())
