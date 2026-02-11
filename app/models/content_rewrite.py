"""Content Rewrite models for AI-powered content optimization."""

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ContentRewrite(Base):
    """Content rewrite request with original content and context."""

    __tablename__ = "content_rewrites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(tz=UTC))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(tz=UTC), onupdate=lambda: datetime.now(tz=UTC)
    )

    # Relationships
    variants: Mapped[list["RewriteVariant"]] = relationship(
        "RewriteVariant", back_populates="rewrite", cascade="all, delete-orphan"
    )


class RewriteVariant(Base):
    """Generated rewrite variant for a content rewrite request."""

    __tablename__ = "rewrite_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rewrite_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("content_rewrites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variant_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Status: pending/approved/rejected
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(tz=UTC))

    # Relationships
    rewrite: Mapped["ContentRewrite"] = relationship("ContentRewrite", back_populates="variants")
