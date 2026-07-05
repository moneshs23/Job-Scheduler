import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class RetryPolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    strategy: str = Field(default="exponential", pattern="^(fixed|linear|exponential|custom)$")
    max_retries: int = Field(default=3, ge=0, le=100)
    base_delay_ms: int = Field(default=1000, ge=0)
    max_delay_ms: int = Field(default=300_000, ge=0)
    multiplier: float = Field(default=2.0, ge=1.0)
    custom_delays: list[int] | None = None


class RetryPolicyResponse(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    strategy: str
    max_retries: int
    base_delay_ms: int
    max_delay_ms: int
    multiplier: float
    custom_delays: dict | list | None


class QueueCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    priority: int = Field(default=0, ge=0, le=100)
    concurrency_limit: int = Field(default=10, ge=1, le=10_000)
    retry_policy_id: uuid.UUID | None = None
    config: dict | None = None


class QueueUpdate(BaseModel):
    priority: int | None = Field(default=None, ge=0, le=100)
    concurrency_limit: int | None = Field(default=None, ge=1, le=10_000)
    retry_policy_id: uuid.UUID | None = None
    config: dict | None = None


class QueueResponse(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    priority: int
    concurrency_limit: int
    is_paused: bool
    retry_policy_id: uuid.UUID | None
    config: dict | None
    created_at: datetime


class QueueMetrics(BaseModel):
    queue_id: uuid.UUID
    queue_name: str
    queued: int
    scheduled: int
    running: int
    completed: int
    failed: int
    retry: int
    dead_letter: int
    is_paused: bool
    concurrency_limit: int
    active_workers: int
    throughput_per_min: float
    avg_latency_ms: float | None
