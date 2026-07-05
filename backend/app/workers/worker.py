import asyncio
import logging
import socket
import uuid
from datetime import datetime, timezone

from app.config.constants import WORKER_STATUS_BUSY, WORKER_STATUS_DRAINING, WORKER_STATUS_IDLE, WORKER_STATUS_STOPPED
from app.config.settings import get_settings
from app.database.session import AsyncSessionLocal
from app.execution.engine import execute_job
from app.monitoring.metrics import JOBS_CLAIMED_TOTAL
from app.queues.redis_client import get_redis
from app.queues.streams import wait_for_notifications
from app.repositories.job import JobRepository
from app.repositories.queue import QueueRepository
from app.repositories.worker import WorkerRepository
from app.services.worker_service import WorkerService

logger = logging.getLogger(__name__)


class WorkerProcess:
    def __init__(
        self,
        project_id: uuid.UUID,
        worker_type: str = "generic",
        concurrency: int | None = None,
        poll_interval_ms: int | None = None,
        heartbeat_interval_sec: int | None = None,
        drain_timeout_sec: int | None = None,
    ):
        settings = get_settings()
        self.project_id = project_id
        self.worker_type = worker_type
        self.hostname = f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
        self.concurrency = concurrency or settings.worker_concurrency
        self.poll_interval_ms = poll_interval_ms or settings.worker_poll_interval_ms
        self.heartbeat_interval_sec = heartbeat_interval_sec or settings.worker_heartbeat_interval_sec
        self.drain_timeout_sec = drain_timeout_sec or settings.worker_drain_timeout_sec

        self.worker_id: uuid.UUID | None = None
        self._draining = False
        self._stop = False
        self._active_tasks: set[asyncio.Task] = set()

    async def start(self) -> None:
        async with AsyncSessionLocal() as db:
            worker = await WorkerService(db).register(
                self.project_id, self.hostname, self.worker_type, self.concurrency, capabilities=None
            )
            self.worker_id = worker.id

        logger.info("Worker %s (%s) registered for project %s", self.worker_id, self.hostname, self.project_id)

        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        try:
            await self._poll_loop()
        finally:
            heartbeat_task.cancel()
            await self._finalize_shutdown()

    def request_shutdown(self) -> None:
        logger.info("Worker %s draining — no new jobs will be claimed", self.worker_id)
        self._draining = True

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval_sec)
                status = WORKER_STATUS_DRAINING if self._draining else (
                    WORKER_STATUS_BUSY if self._active_tasks else WORKER_STATUS_IDLE
                )
                async with AsyncSessionLocal() as db:
                    await WorkerService(db).heartbeat(
                        self.worker_id, status, len(self._active_tasks), None, None, None
                    )
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Heartbeat failed for worker %s", self.worker_id)

    async def _poll_loop(self) -> None:
        redis = get_redis()
        while not self._stop:
            if self._draining and not self._active_tasks:
                break

            available = self.concurrency - len(self._active_tasks)
            claimed_any = False
            if available > 0 and not self._draining:
                claimed_any = await self._claim_and_dispatch(available)

            self._active_tasks = {t for t in self._active_tasks if not t.done()}

            if not claimed_any:
                async with AsyncSessionLocal() as db:
                    queue_ids = [q.id for q in await QueueRepository(db).list_active_for_project(self.project_id)]
                try:
                    await wait_for_notifications(redis, queue_ids, self.poll_interval_ms)
                except Exception:
                    await asyncio.sleep(self.poll_interval_ms / 1000)

    async def _claim_and_dispatch(self, available: int) -> bool:
        dispatched = False
        async with AsyncSessionLocal() as db:
            queues_repo = QueueRepository(db)
            jobs_repo = JobRepository(db)
            queues = await queues_repo.list_active_for_project(self.project_id)

            for queue in queues:
                if available <= 0:
                    break
                active_in_queue = await jobs_repo.count_active_in_queue(queue.id)
                queue_capacity = queue.concurrency_limit - active_in_queue
                claim_limit = min(available, queue_capacity)
                if claim_limit <= 0:
                    continue

                claimed = await jobs_repo.claim_jobs(queue.id, self.worker_id, claim_limit)
                if claimed:
                    JOBS_CLAIMED_TOTAL.labels(queue_id=str(queue.id)).inc(len(claimed))
                for job in claimed:
                    task = asyncio.create_task(execute_job(job.id, self.worker_id))
                    self._active_tasks.add(task)
                    available -= 1
                    dispatched = True
        return dispatched

    async def _finalize_shutdown(self) -> None:
        if self._active_tasks:
            await asyncio.wait(self._active_tasks, timeout=self.drain_timeout_sec)

        async with AsyncSessionLocal() as db:
            worker = await WorkerRepository(db).get(self.worker_id)
            if worker is not None:
                worker.status = WORKER_STATUS_STOPPED
                worker.last_heartbeat_at = datetime.now(timezone.utc)
                await db.commit()
        logger.info("Worker %s stopped", self.worker_id)
