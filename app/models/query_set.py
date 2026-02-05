# app/models/query_set.py

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company_profile import CompanyProfile
    from app.models.pipeline_category import PipelineCategory
    from app.models.pipeline_job import PipelineJob
    from app.models.user import User


class QuerySet(Base, TimestampMixin):
    """Reusable query template for time-series analysis."""

    __tablename__ = "query_sets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Configuration snapshot
    category_count: Mapped[int] = mapped_column(Integer, nullable=False)
    queries_per_category: Mapped[int] = mapped_column(Integer, nullable=False)

    # Foreign Keys
    company_profile_id: Mapped[int] = mapped_column(
        ForeignKey("company_profiles.id"), nullable=False
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )

    # Relationships
    company_profile: Mapped["CompanyProfile"] = relationship(
        "CompanyProfile", back_populates="query_sets"
    )
    owner: Mapped["User"] = relationship("User", backref="query_sets")
    categories: Mapped[list["PipelineCategory"]] = relationship(
        "PipelineCategory", back_populates="query_set", cascade="all, delete-orphan"
    )
    pipeline_jobs: Mapped[list["PipelineJob"]] = relationship(
        "PipelineJob", back_populates="query_set", cascade="all, delete-orphan"
    )
