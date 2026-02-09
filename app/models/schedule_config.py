# app/models/schedule_config.py

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.query_set import QuerySet
    from app.models.user import User


class ScheduleConfig(Base, TimestampMixin):
    """Schedule configuration for automated pipeline reruns."""

    __tablename__ = "schedule_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    llm_providers: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Foreign Keys
    query_set_id: Mapped[int] = mapped_column(
        ForeignKey("query_sets.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Relationships
    query_set: Mapped["QuerySet"] = relationship("QuerySet", backref="schedule_config")
    owner: Mapped["User"] = relationship("User", backref="schedule_configs")
