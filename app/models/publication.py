"""Publication models for SNS publishing."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Publication(Base, TimestampMixin):
    """Publication record for SNS posts."""

    __tablename__ = "publications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="draft", index=True
    )  # draft/scheduled/published/failed
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    external_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Platform's post ID
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class PublishQueue(Base, TimestampMixin):
    """Queue for retrying failed publications."""

    __tablename__ = "publish_queue"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    publication_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("publications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
