"""RunCitation model for tracking citations in LLM responses."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.campaign import RunResponse
    from app.models.gallery import CitationReview
    from app.models.user import User


class RunCitation(Base, TimestampMixin):
    """Citation extracted from a run response."""
    __tablename__ = "run_citations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_response_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("run_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cited_brand: Mapped[str] = mapped_column(String(255), nullable=False)
    citation_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    citation_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    citation_span: Mapped[str] = mapped_column(Text, nullable=False)
    context_before: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_after: Mapped[str | None] = mapped_column(Text, nullable=True)
    position_in_response: Mapped[int] = mapped_column(Integer, nullable=False)
    is_target_brand: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    run_response: Mapped["RunResponse"] = relationship(
        "RunResponse", back_populates="run_citations"
    )
    verifier: Mapped["User | None"] = relationship("User", foreign_keys=[verified_by])
    citation_reviews: Mapped[list["CitationReview"]] = relationship(
        "CitationReview", back_populates="run_citation", cascade="all, delete-orphan"
    )
