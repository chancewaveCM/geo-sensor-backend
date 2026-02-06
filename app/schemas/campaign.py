"""Pydantic schemas for Campaign operations."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# --- Campaign ---


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    schedule_interval_hours: int = Field(default=24, ge=1, le=720)
    schedule_enabled: bool = False


class CampaignUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    schedule_interval_hours: int | None = Field(None, ge=1, le=720)
    schedule_enabled: bool | None = None
    status: str | None = Field(None, pattern="^(active|paused|archived)$")


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    description: str | None = None
    owner_id: int
    schedule_interval_hours: int
    schedule_enabled: bool
    schedule_next_run_at: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class CampaignDetailResponse(CampaignResponse):
    """Campaign with counts."""

    query_count: int | None = None
    run_count: int | None = None
    company_count: int | None = None


# --- IntentCluster ---


class IntentClusterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    order_index: int = 0


class IntentClusterUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    order_index: int | None = None


class IntentClusterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    campaign_id: int
    order_index: int
    created_at: datetime


# --- QueryDefinition ---


class QueryDefinitionCreate(BaseModel):
    query_type: str = Field(..., pattern="^(anchor|exploration)$")
    intent_cluster_id: int | None = None
    text: str = Field(..., min_length=1, description="Initial query text (creates v1)")
    persona_type: str | None = Field(None, pattern="^(consumer|investor)$")


class QueryDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    intent_cluster_id: int | None = None
    query_type: str
    current_version: int
    is_active: bool
    is_retired: bool
    created_by: int
    created_at: datetime


# --- QueryVersion ---


class QueryVersionCreate(BaseModel):
    text: str = Field(..., min_length=1)
    persona_type: str | None = None
    change_reason: str | None = None


class QueryVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query_definition_id: int
    version: int
    text: str
    persona_type: str | None = None
    change_reason: str | None = None
    changed_by: int
    is_current: bool
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    created_at: datetime


# --- CampaignRun ---


class CampaignRunCreate(BaseModel):
    llm_providers: list[str] = Field(default=["openai", "gemini"])


class CampaignRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    run_number: int
    trigger_type: str
    llm_providers: str | None = None
    status: str
    total_queries: int
    completed_queries: int
    failed_queries: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


# --- CampaignCompany ---


class CampaignCompanyCreate(BaseModel):
    company_profile_id: int
    is_target_brand: bool = False
    notes: str | None = None


class CampaignCompanyUpdate(BaseModel):
    is_target_brand: bool | None = None
    display_order: int | None = None
    notes: str | None = None


class CampaignCompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    company_profile_id: int
    is_target_brand: bool
    display_order: int
    added_by: int
    notes: str | None = None
    created_at: datetime
    # Populated from join:
    company_name: str | None = None


# --- RunResponse ---


class RunResponseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_run_id: int
    query_version_id: int
    llm_provider: str
    llm_model: str
    word_count: int | None = None
    citation_count: int | None = None
    latency_ms: float
    created_at: datetime


# --- Timeseries ---


class TimeseriesDataPoint(BaseModel):
    run_id: int
    timestamp: datetime
    citation_share_overall: float
    citation_share_by_provider: dict[str, float] | None = None
    total_citations: int
    brand_citations: int


class TimeseriesResponse(BaseModel):
    campaign_id: int
    brand_name: str
    time_series: list[TimeseriesDataPoint]
    annotations: list[dict] = []


class CampaignSummaryResponse(BaseModel):
    campaign_id: int
    total_runs: int
    total_responses: int
    total_citations: int
    latest_run: CampaignRunResponse | None = None
    citation_share_by_brand: dict[str, float] = {}
