"""Generated Query model."""

from enum import Enum

import sqlalchemy as sa
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class QueryCategory(str, Enum):
    INTRODUCTORY = "introductory"  # 1-10
    COMPARATIVE = "comparative"    # 11-20
    CRITICAL = "critical"          # 21-30


class GeneratedQueryStatus(str, Enum):
    GENERATED = "generated"
    EDITED = "edited"
    SELECTED = "selected"
    EXCLUDED = "excluded"


class GeneratedQuery(Base, TimestampMixin):
    """AI-generated query for company analysis."""

    __tablename__ = "generated_queries"

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    text = sa.Column(sa.Text, nullable=False)
    order_index = sa.Column(sa.Integer, nullable=False)  # 1-30
    category = sa.Column(sa.String(50), nullable=False)
    status = sa.Column(sa.String(50), default=GeneratedQueryStatus.GENERATED.value)
    is_selected = sa.Column(sa.Boolean, default=True)
    original_text = sa.Column(sa.Text)  # 편집 전 원본 저장

    company_profile_id = sa.Column(
        sa.Integer, sa.ForeignKey("company_profiles.id"), nullable=False
    )

    # Relationships
    company_profile = relationship("CompanyProfile", back_populates="generated_queries")
