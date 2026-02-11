"""Notification models for campaign alerts and webhooks."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.workspace import Workspace


class NotificationConfig(Base, TimestampMixin):
    """Notification configuration for campaigns."""

    __tablename__ = "notification_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # email, webhook
    destination: Mapped[str] = mapped_column(String(500), nullable=False)  # email or URL
    events: Mapped[str] = mapped_column(Text, nullable=False)  # JSON array of event types
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Alert rule fields (optional)
    threshold_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    threshold_value: Mapped[float | None] = mapped_column(nullable=True)
    comparison: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    logs: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog", back_populates="config", cascade="all, delete-orphan"
    )


class NotificationLog(Base, TimestampMixin):
    """Log of notification deliveries."""

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    notification_config_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("notification_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)  # JSON payload
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # pending, sent, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    config: Mapped["NotificationConfig"] = relationship(
        "NotificationConfig", back_populates="logs"
    )
