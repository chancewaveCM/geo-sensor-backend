# app/models/dead_letter.py

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.pipeline_job import PipelineJob


class DeadLetterJob(Base, TimestampMixin):
    """Dead letter queue for failed pipeline jobs with retry tracking."""

    __tablename__ = "dead_letter_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Foreign key to original job
    job_id: Mapped[int] = mapped_column(
        sa.ForeignKey("pipeline_jobs.id"), nullable=False, index=True
    )

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(sa.Integer, default=0, server_default="0")
    max_retries: Mapped[int] = mapped_column(sa.Integer, default=3, server_default="3")

    # Timing
    failed_at: Mapped[datetime] = mapped_column(sa.DateTime, nullable=False)
    last_retry_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)

    # Status: "failed" | "retrying" | "exhausted"
    status: Mapped[str] = mapped_column(
        sa.String(20), default="failed", server_default="failed"
    )

    # Relationship
    pipeline_job: Mapped["PipelineJob"] = relationship("PipelineJob", backref="dead_letter_jobs")
