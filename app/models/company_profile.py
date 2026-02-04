"""Company Profile model."""

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


class CompanyProfile(Base, TimestampMixin):
    """Company profile for analysis."""

    __tablename__ = "company_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    industry = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    target_audience = Column(Text)
    main_products = Column(Text)
    competitors = Column(Text)
    unique_value = Column(Text)
    website_url = Column(String(500))

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationships
    owner = relationship("User", backref="company_profiles")
    project = relationship("Project", backref="company_profiles")
    generated_queries = relationship(
        "GeneratedQuery",
        back_populates="company_profile",
        cascade="all, delete-orphan",
    )
