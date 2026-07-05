import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import WORKER_STATUS_STARTING
from app.models.worker import Worker, WorkerHeartbeat
from app.repositories.worker import WorkerHeartbeatRepository, WorkerRepository


class WorkerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.workers = WorkerRepository(db)
        self.heartbeats = WorkerHeartbeatRepository(db)

    async def register(
        self, project_id: uuid.UUID, hostname: str, worker_type: str, concurrency: int, capabilities: dict | None
    ) -> Worker:
        worker = await self.workers.add(
            Worker(
                project_id=project_id,
                hostname=hostname,
                worker_type=worker_type,
                status=WORKER_STATUS_STARTING,
                concurrency=concurrency,
                capabilities=capabilities,
                last_heartbeat_at=datetime.now(timezone.utc),
            )
        )
        await self.db.commit()
        return worker

    async def heartbeat(
        self,
        worker_id: uuid.UUID,
        status_value: str,
        active_jobs: int,
        cpu_percent: float | None,
        memory_mb: float | None,
        metadata: dict | None,
    ) -> Worker:
        worker = await self.workers.get(worker_id)
        if worker is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Worker not found")

        now = datetime.now(timezone.utc)
        worker.status = status_value
        worker.active_jobs = active_jobs
        worker.last_heartbeat_at = now

        await self.heartbeats.add(
            WorkerHeartbeat(
                worker_id=worker_id,
                status=status_value,
                active_jobs=active_jobs,
                cpu_percent=cpu_percent,
                memory_mb=memory_mb,
                heartbeat_metadata=metadata,
                heartbeat_at=now,
            )
        )
        await self.db.commit()
        return worker

    async def list_for_project(self, project_id: uuid.UUID) -> list[Worker]:
        return await self.workers.list_for_project(project_id)

    async def request_shutdown(self, worker_id: uuid.UUID) -> Worker:
        worker = await self.workers.get(worker_id)
        if worker is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Worker not found")
        worker.status = "draining"
        await self.db.commit()
        return worker
