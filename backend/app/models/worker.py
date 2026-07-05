import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import WORKER_STATUS_STARTING
from app.models.base import Base, UUIDPrimaryKeyMixin


class Worker(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "workers"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    worker_type: Mapped[str] = mapped_column(String(100), default="generic", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=WORKER_STATUS_STARTING, nullable=False, index=True)
    concurrency: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    active_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    capabilities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    project: Mapped["Project"] = relationship(back_populates="workers")
    claimed_jobs: Mapped[list["Job"]] = relationship(back_populates="worker")
    heartbeats: Mapped[list["WorkerHeartbeat"]] = relationship(
        back_populates="worker", cascade="all, delete-orphan"
    )
    executions: Mapped[list["JobExecution"]] = relationship(back_populates="worker")


class WorkerHeartbeat(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    active_jobs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    memory_mb: Mapped[float | None] = mapped_column(Float, nullable=True)
    heartbeat_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    worker: Mapped["Worker"] = relationship(back_populates="heartbeats")


from app.models.job import Job  # noqa: E402
from app.models.organization import Project  # noqa: E402
from app.models.execution import JobExecution  # noqa: E402
