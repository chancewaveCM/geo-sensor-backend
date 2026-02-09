"""Insight model for auto-generated campaign insights."""
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Insight(Base, TimestampMixin):
    """Auto-generated insight from campaign data analysis."""

    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    insight_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # provider_gap, citation_drop, positive_trend
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # info, warning, critical
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    data_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON string with detail data
    is_dismissed: Mapped[bool] = mapped_column(default=False, nullable=False)
