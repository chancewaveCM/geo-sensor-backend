# app/models/raw_llm_response.py

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.expanded_query import ExpandedQuery
    from app.models.pipeline_job import PipelineJob


class RawLLMResponse(Base, TimestampMixin):
    """Raw response from LLM provider - normalized storage."""

    __tablename__ = "raw_llm_responses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Response content
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)

    # Provider info (uses canonical LLMProvider from enums.py)
    llm_provider: Mapped[str] = mapped_column(
        sa.String(50), nullable=False
    )
    llm_model: Mapped[str] = mapped_column(sa.String(100), nullable=False)

    # Metadata (normalized across providers)
    tokens_used: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    # Raw response for debugging (JSON)
    raw_response_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(sa.Integer, default=0)

    # Foreign Keys
    query_id: Mapped[int] = mapped_column(
        sa.ForeignKey("expanded_queries.id"), nullable=False
    )
    pipeline_job_id: Mapped[int] = mapped_column(
        sa.ForeignKey("pipeline_jobs.id"), nullable=False
    )

    # Relationships
    query: Mapped["ExpandedQuery"] = relationship(
        "ExpandedQuery", back_populates="raw_responses"
    )
    pipeline_job: Mapped["PipelineJob"] = relationship(
        "PipelineJob", back_populates="responses"
    )
