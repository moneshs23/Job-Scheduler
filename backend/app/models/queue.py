import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class RetryPolicy(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "retry_policies"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    strategy: Mapped[str] = mapped_column(String(50), default="exponential", nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    base_delay_ms: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    max_delay_ms: Mapped[int] = mapped_column(Integer, default=300000, nullable=False)
    multiplier: Mapped[float] = mapped_column(default=2.0, nullable=False)
    custom_delays: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="retry_policies")
    queues: Mapped[list["Queue"]] = relationship(back_populates="retry_policy")


class Queue(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "queues"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_queue_name"),
        {"comment": "Job queues with priority and concurrency"},
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    concurrency_limit: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_paused: Mapped[bool] = mapped_column(default=False, nullable=False)
    retry_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("retry_policies.id", ondelete="SET NULL"), nullable=True
    )
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="queues")
    retry_policy: Mapped["RetryPolicy | None"] = relationship(back_populates="queues")
    jobs: Mapped[list["Job"]] = relationship(back_populates="queue")
    dead_letter_entries: Mapped[list["DeadLetterEntry"]] = relationship(back_populates="queue")


from app.models.dead_letter import DeadLetterEntry  # noqa: E402
from app.models.job import Job  # noqa: E402
from app.models.organization import Project  # noqa: E402
