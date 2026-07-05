import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import JOB_STATUS_QUEUED
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Job(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_project_idempotency_key"),
        # Composite index driving the SKIP LOCKED claim query: queue + status + priority + schedule.
        Index("ix_jobs_claim_candidates", "queue_id", "status", "priority", "scheduled_at"),
        Index("ix_jobs_project_status", "project_id", "status"),
        CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count_nonneg"),
    )

    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("queues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=JOB_STATUS_QUEUED, nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    job_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workers.id", ondelete="SET NULL"), nullable=True
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    queue: Mapped["Queue"] = relationship(back_populates="jobs")
    project: Mapped["Project"] = relationship(back_populates="jobs")
    worker: Mapped["Worker | None"] = relationship(back_populates="claimed_jobs")
    schedule: Mapped["ScheduledJob | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )
    executions: Mapped[list["JobExecution"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobExecution.attempt_number"
    )
    logs: Mapped[list["JobLog"]] = relationship(back_populates="job", cascade="all, delete-orphan")
    dead_letter: Mapped["DeadLetterEntry | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )


class ScheduledJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "scheduled_jobs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    schedule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(255), nullable=True)
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="schedule")


from app.models.organization import Project  # noqa: E402
from app.models.queue import Queue  # noqa: E402
from app.models.worker import Worker  # noqa: E402
from app.models.execution import JobExecution, JobLog  # noqa: E402
from app.models.dead_letter import DeadLetterEntry  # noqa: E402
