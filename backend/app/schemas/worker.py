import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class WorkerRegisterRequest(BaseModel):
    hostname: str
    worker_type: str = "generic"
    concurrency: int = 10
    capabilities: dict | None = None


class WorkerHeartbeatRequest(BaseModel):
    status: str
    active_jobs: int = 0
    cpu_percent: float | None = None
    memory_mb: float | None = None
    metadata: dict | None = None


class WorkerResponse(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    hostname: str
    worker_type: str
    status: str
    concurrency: int
    active_jobs: int
    capabilities: dict | None
    registered_at: datetime
    last_heartbeat_at: datetime | None


class WorkerHeartbeatResponse(ORMModel):
    id: uuid.UUID
    worker_id: uuid.UUID
    status: str
    active_jobs: int
    cpu_percent: float | None
    memory_mb: float | None
    heartbeat_at: datetime
