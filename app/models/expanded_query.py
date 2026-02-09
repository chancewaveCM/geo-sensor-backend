# app/models/expanded_query.py

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ExpandedQueryStatus

if TYPE_CHECKING:
    from app.models.pipeline_category import PipelineCategory
    from app.models.raw_llm_response import RawLLMResponse


class ExpandedQuery(Base, TimestampMixin):
    """Query expanded from a category."""

    __tablename__ = "expanded_queries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    order_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(50), default=ExpandedQueryStatus.PENDING.value
    )

    # Foreign Keys
    category_id: Mapped[int] = mapped_column(
        sa.ForeignKey("pipeline_categories.id"), nullable=False
    )

    # Relationships
    category: Mapped["PipelineCategory"] = relationship(
        "PipelineCategory", back_populates="expanded_queries"
    )
    raw_responses: Mapped[list["RawLLMResponse"]] = relationship(
        "RawLLMResponse", back_populates="query", cascade="all, delete-orphan"
    )
