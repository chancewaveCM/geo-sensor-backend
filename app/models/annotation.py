"""CampaignAnnotation model for marking events on timeseries charts."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CampaignAnnotation(Base, TimestampMixin):
    """Annotation on a campaign timeseries (e.g. query change, model change)."""

    __tablename__ = "campaign_annotations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    annotation_type: Mapped[str] = mapped_column(
        String(50), default="manual", nullable=False
    )
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    # Relationships
    campaign = relationship("Campaign")
    creator = relationship("User", foreign_keys=[created_by_id])
