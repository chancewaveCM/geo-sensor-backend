# app/models/pipeline_job.py

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PipelineStatus

if TYPE_CHECKING:
    from app.models.company_profile import CompanyProfile
    from app.models.query_set import QuerySet
    from app.models.raw_llm_response import RawLLMResponse
    from app.models.user import User


class PipelineJob(Base, TimestampMixin):
    """Background job for query pipeline execution."""

    __tablename__ = "pipeline_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Configuration
    llm_providers: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # ["gemini", "openai"]

    # Status tracking
    status: Mapped[PipelineStatus] = mapped_column(
        SQLEnum(PipelineStatus), default=PipelineStatus.PENDING
    )

    # Progress tracking
    total_queries: Mapped[int] = mapped_column(Integer, default=0)
    completed_queries: Mapped[int] = mapped_column(Integer, default=0)
    failed_queries: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Error info
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign Keys
    query_set_id: Mapped[int] = mapped_column(
        ForeignKey("query_sets.id"), nullable=False
    )
    company_profile_id: Mapped[int] = mapped_column(
        ForeignKey("company_profiles.id"), nullable=False
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    # Relationships
    query_set: Mapped["QuerySet"] = relationship(
        "QuerySet", back_populates="pipeline_jobs"
    )
    company_profile: Mapped["CompanyProfile"] = relationship(
        "CompanyProfile", back_populates="pipeline_jobs"
    )
    owner: Mapped["User"] = relationship("User", backref="pipeline_jobs")
    responses: Mapped[list["RawLLMResponse"]] = relationship(
        "RawLLMResponse", back_populates="pipeline_job", cascade="all, delete-orphan"
    )
