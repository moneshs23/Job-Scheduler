import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class JobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    queue_id: uuid.UUID
    payload: dict | None = None
    priority: int = Field(default=0, ge=0, le=100)
    max_attempts: int = Field(default=3, ge=1, le=50)
    idempotency_key: str | None = None

    # Delayed / scheduled / cron / recurring — only one may be set.
    run_at: datetime | None = None
    delay_seconds: int | None = Field(default=None, ge=0)
    cron_expression: str | None = None

    @model_validator(mode="after")
    def check_schedule_exclusive(self) -> "JobCreate":
        provided = [v is not None for v in (self.run_at, self.delay_seconds, self.cron_expression)]
        if sum(provided) > 1:
            raise ValueError("Only one of run_at, delay_seconds, cron_expression may be set")
        return self


class BatchJobCreate(BaseModel):
    queue_id: uuid.UUID
    jobs: list[JobCreate] = Field(min_length=1, max_length=10_000)


class JobResponse(ORMModel):
    id: uuid.UUID
    queue_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    status: str
    priority: int
    payload: dict | None
    idempotency_key: str | None
    attempt_count: int
    max_attempts: int
    worker_id: uuid.UUID | None
    batch_id: uuid.UUID | None
    scheduled_at: datetime | None
    claimed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    next_retry_at: datetime | None
    last_error: str | None
    created_at: datetime


class JobExecutionResponse(ORMModel):
    id: uuid.UUID
    job_id: uuid.UUID
    worker_id: uuid.UUID | None
    attempt_number: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    result: dict | None
    error_message: str | None
    error_stack: str | None


class JobLogResponse(ORMModel):
    id: uuid.UUID
    job_id: uuid.UUID
    execution_id: uuid.UUID | None
    level: str
    message: str
    context: dict | None
    logged_at: datetime


class DeadLetterResponse(ORMModel):
    id: uuid.UUID
    job_id: uuid.UUID
    queue_id: uuid.UUID
    original_payload: dict | None
    failure_reason: str | None
    total_attempts: int
    moved_at: datetime
    replayed_at: datetime | None
