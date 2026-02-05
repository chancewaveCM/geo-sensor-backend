# app/models/pipeline_category.py

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import PersonaType

if TYPE_CHECKING:
    from app.models.company_profile import CompanyProfile
    from app.models.expanded_query import ExpandedQuery
    from app.models.query_set import QuerySet


class PipelineCategory(Base, TimestampMixin):
    """Generated category for query expansion in pipeline."""

    __tablename__ = "pipeline_categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    persona_type: Mapped[PersonaType] = mapped_column(
        SQLEnum(PersonaType), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Foreign Keys
    company_profile_id: Mapped[int] = mapped_column(
        ForeignKey("company_profiles.id"), nullable=False
    )
    query_set_id: Mapped[int] = mapped_column(
        ForeignKey("query_sets.id"), nullable=False
    )

    # Relationships
    company_profile: Mapped["CompanyProfile"] = relationship(
        "CompanyProfile", back_populates="pipeline_categories"
    )
    query_set: Mapped["QuerySet"] = relationship(
        "QuerySet", back_populates="categories"
    )
    expanded_queries: Mapped[list["ExpandedQuery"]] = relationship(
        "ExpandedQuery", back_populates="category", cascade="all, delete-orphan"
    )
