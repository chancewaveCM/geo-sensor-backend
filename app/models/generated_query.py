"""Generated Query model."""

from enum import Enum

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text
from sqlalchemy import Enum as SQLEnum
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

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False)  # 1-30
    category = Column(SQLEnum(QueryCategory), nullable=False)
    status = Column(SQLEnum(GeneratedQueryStatus), default=GeneratedQueryStatus.GENERATED)
    is_selected = Column(Boolean, default=True)
    original_text = Column(Text)  # 편집 전 원본 저장

    company_profile_id = Column(Integer, ForeignKey("company_profiles.id"), nullable=False)

    # Relationships
    company_profile = relationship("CompanyProfile", back_populates="generated_queries")
