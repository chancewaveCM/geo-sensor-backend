"""Gallery-related models: labels, reviews, comparisons, and operation logs."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import OperationStatus

if TYPE_CHECKING:
    from app.models.campaign import RunResponse
    from app.models.run_citation import RunCitation
    from app.models.user import User
    from app.models.workspace import Workspace


class ResponseLabel(Base, TimestampMixin):
    """Label applied to a run response for categorization/flagging."""
    __tablename__ = "response_labels"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workspaces.id"), nullable=False, index=True
    )
    run_response_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("run_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label_type: Mapped[str] = mapped_column(String(20), nullable=False)
    label_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    run_response: Mapped["RunResponse"] = relationship(
        "RunResponse", back_populates="response_labels"
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    resolver: Mapped["User | None"] = relationship("User", foreign_keys=[resolved_by])


class CitationReview(Base, TimestampMixin):
    """Review of a citation (false positive, etc.)."""
    __tablename__ = "citation_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_citation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("run_citations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Relationships
    run_citation: Mapped["RunCitation"] = relationship(
        "RunCitation", back_populates="citation_reviews"
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])


class ComparisonSnapshot(Base, TimestampMixin):
    """Snapshot for comparing different runs/LLMs/dates."""
    __tablename__ = "comparison_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    comparison_type: Mapped[str] = mapped_column(String(30), nullable=False)
    config: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])


class OperationLog(Base, TimestampMixin):
    """Log of operations requiring approval or tracking."""
    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workspaces.id"), nullable=False, index=True
    )
    operation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default=OperationStatus.PENDING.value, nullable=False
    )
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by])
