"""Campaign-related models for GEO Sensor backend."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import CampaignStatus, RunStatus

if TYPE_CHECKING:
    from app.models.company_profile import CompanyProfile
    from app.models.gallery import ResponseLabel
    from app.models.run_citation import RunCitation
    from app.models.user import User
    from app.models.workspace import Workspace


class Campaign(Base, TimestampMixin):
    """Campaign model for managing query collections and runs."""
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    schedule_interval_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schedule_next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=CampaignStatus.ACTIVE.value, nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    intent_clusters: Mapped[list["IntentCluster"]] = relationship(
        "IntentCluster", back_populates="campaign", cascade="all, delete-orphan"
    )
    query_definitions: Mapped[list["QueryDefinition"]] = relationship(
        "QueryDefinition", back_populates="campaign", cascade="all, delete-orphan"
    )
    campaign_runs: Mapped[list["CampaignRun"]] = relationship(
        "CampaignRun", back_populates="campaign", cascade="all, delete-orphan"
    )
    campaign_companies: Mapped[list["CampaignCompany"]] = relationship(
        "CampaignCompany", back_populates="campaign", cascade="all, delete-orphan"
    )
    prompt_templates: Mapped[list["PromptTemplate"]] = relationship(
        "PromptTemplate", back_populates="campaign", cascade="all, delete-orphan"
    )


class IntentCluster(Base, TimestampMixin):
    """Intent cluster for organizing queries."""
    __tablename__ = "intent_clusters"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="intent_clusters")
    query_definitions: Mapped[list["QueryDefinition"]] = relationship(
        "QueryDefinition", back_populates="intent_cluster"
    )


class QueryDefinition(Base, TimestampMixin):
    """Query definition model."""
    __tablename__ = "query_definitions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intent_cluster_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("intent_clusters.id"), nullable=True, index=True
    )
    query_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_retired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="query_definitions")
    intent_cluster: Mapped["IntentCluster | None"] = relationship(
        "IntentCluster", back_populates="query_definitions"
    )
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    query_versions: Mapped[list["QueryVersion"]] = relationship(
        "QueryVersion", back_populates="query_definition", cascade="all, delete-orphan"
    )


class QueryVersion(Base, TimestampMixin):
    """Query version model for tracking query text changes."""
    __tablename__ = "query_versions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    query_definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("query_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    persona_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    query_definition: Mapped["QueryDefinition"] = relationship(
        "QueryDefinition", back_populates="query_versions"
    )
    changer: Mapped["User"] = relationship("User", foreign_keys=[changed_by])
    run_responses: Mapped[list["RunResponse"]] = relationship(
        "RunResponse", back_populates="query_version"
    )


class PromptTemplate(Base, TimestampMixin):
    """Prompt template model for versioning prompts."""
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    template_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="prompt_templates")
    changer: Mapped["User"] = relationship("User", foreign_keys=[changed_by])
    campaign_runs: Mapped[list["CampaignRun"]] = relationship(
        "CampaignRun", back_populates="prompt_version"
    )


class CampaignRun(Base, TimestampMixin):
    """Campaign run model for tracking execution."""
    __tablename__ = "campaign_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )
    llm_providers: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    status: Mapped[str] = mapped_column(
        String(20), default=RunStatus.PENDING.value, nullable=False
    )
    prompt_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("prompt_templates.id"), nullable=True
    )
    total_queries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_queries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_queries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="campaign_runs")
    prompt_version: Mapped["PromptTemplate | None"] = relationship(
        "PromptTemplate", back_populates="campaign_runs"
    )
    run_responses: Mapped[list["RunResponse"]] = relationship(
        "RunResponse", back_populates="campaign_run", cascade="all, delete-orphan"
    )


class RunResponse(Base, TimestampMixin):
    """Run response model for storing LLM responses."""
    __tablename__ = "run_responses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaign_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("query_versions.id"), nullable=False, index=True
    )
    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)
    llm_model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    raw_response_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    campaign_run: Mapped["CampaignRun"] = relationship(
        "CampaignRun", back_populates="run_responses"
    )
    query_version: Mapped["QueryVersion"] = relationship(
        "QueryVersion", back_populates="run_responses"
    )
    run_citations: Mapped[list["RunCitation"]] = relationship(
        "RunCitation", back_populates="run_response", cascade="all, delete-orphan"
    )
    response_labels: Mapped[list["ResponseLabel"]] = relationship(
        "ResponseLabel", back_populates="run_response", cascade="all, delete-orphan"
    )


class CampaignCompany(Base, TimestampMixin):
    """Campaign-Company M2M relationship."""
    __tablename__ = "campaign_companies"
    __table_args__ = (
        UniqueConstraint("campaign_id", "company_profile_id", name="uq_campaign_company"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_target_brand: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    added_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="campaign_companies")
    company_profile: Mapped["CompanyProfile"] = relationship("CompanyProfile")
    adder: Mapped["User"] = relationship("User", foreign_keys=[added_by])
