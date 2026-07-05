from datetime import datetime

from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_jobs: int
    queued_jobs: int
    running_jobs: int
    completed_jobs: int
    failed_jobs: int
    dead_letter_jobs: int
    active_workers: int
    total_workers: int
    active_queues: int
    paused_queues: int
    throughput_per_min: float
    failure_rate_pct: float


class ThroughputPoint(BaseModel):
    bucket: datetime
    completed: int
    failed: int
    retried: int


class LatencyPoint(BaseModel):
    bucket: datetime
    p50_ms: float
    p95_ms: float
    p99_ms: float
