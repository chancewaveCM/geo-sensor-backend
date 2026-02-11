"""Pipeline API schemas.

Pydantic models for pipeline endpoints including jobs, query sets,
categories, queries, responses, stats, and schedules.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ============ Pipeline Job Schemas ============


class StartPipelineRequest(BaseModel):
    company_profile_id: int
    category_count: int = Field(default=10, ge=1, le=20)
    queries_per_category: int = Field(default=10, ge=1, le=20)
    llm_providers: list[str] = Field(
        default=["gemini", "openai"],
        min_length=1,
        max_length=2,
    )


class StartPipelineResponse(BaseModel):
    job_id: int
    status: str
    message: str
    estimated_queries: int


class PipelineJobStatusResponse(BaseModel):
    id: int
    status: str
    company_profile_id: int
    query_set_id: int  # FIX #6: Reference QuerySet instead of storing config directly
    llm_providers: list[str]
    total_queries: int
    completed_queries: int
    failed_queries: int
    progress_percentage: float
    started_at: datetime | None
    completed_at: datetime | None
    elapsed_seconds: float | None
    error_message: str | None

    class Config:
        from_attributes = True


class PipelineJobSummary(BaseModel):
    id: int
    status: str
    company_profile_id: int
    company_name: str | None = None
    query_set_id: int | None = None
    query_set_name: str | None = None
    llm_providers: list[str]
    total_queries: int
    completed_queries: int
    failed_queries: int
    progress_percentage: float
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class PipelineJobListResponse(BaseModel):
    jobs: list[PipelineJobSummary]
    total: int


class CancelJobResponse(BaseModel):
    job_id: int
    status: str
    message: str


# ============ QuerySet Schemas ============


class QuerySetResponse(BaseModel):
    id: int
    name: str
    description: str | None
    category_count: int
    queries_per_category: int
    company_profile_id: int
    created_at: datetime
    job_count: int  # Number of PipelineJobs that used this QuerySet
    last_job_status: str | None = None
    last_run_at: datetime | None = None
    total_responses: int = 0

    class Config:
        from_attributes = True


class QuerySetListResponse(BaseModel):
    query_sets: list[QuerySetResponse]
    total: int


class QuerySetHistoryItem(BaseModel):
    job_id: int
    status: str
    completed_queries: int
    failed_queries: int
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class QuerySetHistoryResponse(BaseModel):
    query_set_id: int
    query_set_name: str
    executions: list[QuerySetHistoryItem]
    total_executions: int


class QuerySetDetailCategoryItem(BaseModel):
    id: int
    name: str
    description: str | None
    llm_provider: str
    persona_type: str
    order_index: int
    query_count: int

    class Config:
        from_attributes = True


class QuerySetDetailJobItem(BaseModel):
    id: int
    status: str
    llm_providers: list[str]
    total_queries: int
    completed_queries: int
    failed_queries: int
    started_at: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


class QuerySetDetailResponse(BaseModel):
    id: int
    name: str
    description: str | None
    category_count: int
    queries_per_category: int
    company_profile_id: int
    created_at: datetime
    categories: list[QuerySetDetailCategoryItem]
    last_job: QuerySetDetailJobItem | None
    total_jobs: int
    total_responses: int

    class Config:
        from_attributes = True


class RerunQuerySetRequest(BaseModel):
    llm_providers: list[str] = Field(
        default=["gemini", "openai"],
        min_length=1,
        max_length=2,
    )


# ============ Category Schemas ============


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: str | None
    llm_provider: str
    persona_type: str
    order_index: int
    query_count: int

    class Config:
        from_attributes = True


class CategoriesListResponse(BaseModel):
    categories: list[CategoryResponse]


class UpdateCategoryRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class CreateCategoryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    persona_type: str = Field(default="consumer")
    llm_provider: str = Field(default="gemini")
    order_index: int = Field(default=0, ge=0)


# ============ Query Schemas ============


class ExpandedQueryResponse(BaseModel):
    id: int
    text: str
    order_index: int
    status: str
    category_id: int
    response_count: int

    class Config:
        from_attributes = True


class QueriesListResponse(BaseModel):
    queries: list[ExpandedQueryResponse]
    total: int


# ============ Response Schemas ============


class RawResponseResponse(BaseModel):
    id: int
    content: str
    llm_provider: str
    llm_model: str
    tokens_used: int | None
    latency_ms: float | None
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ResponsesListResponse(BaseModel):
    responses: list[RawResponseResponse]


# ============ Stats Schemas ============


class CompanyProfilePipelineStats(BaseModel):
    company_profile_id: int
    company_name: str
    total_query_sets: int
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    success_rate_30d: float  # percentage 0-100
    last_run_status: str | None  # most recent job status
    last_run_at: datetime | None  # most recent job started_at
    avg_processing_time_seconds: float | None  # avg of completed jobs
    data_freshness_hours: float | None  # hours since last successful completion
    health_grade: Literal["green", "yellow", "red"]

    class Config:
        from_attributes = True


class ProfileStatsListResponse(BaseModel):
    profiles: list[CompanyProfilePipelineStats]
    total: int


# ============ Schedule Schemas ============


class CreateScheduleRequest(BaseModel):
    query_set_id: int
    interval_minutes: int = Field(..., ge=60, le=43200, description="60 min to 30 days")
    llm_providers: list[str] = Field(
        default=["gemini", "openai"],
        min_length=1,
        max_length=2,
    )
    is_active: bool = True


class UpdateScheduleRequest(BaseModel):
    interval_minutes: int | None = Field(default=None, ge=60, le=43200)
    llm_providers: list[str] | None = Field(default=None, min_length=1, max_length=2)
    is_active: bool | None = None


class ScheduleConfigResponse(BaseModel):
    id: int
    query_set_id: int
    query_set_name: str
    company_profile_id: int
    company_name: str
    interval_minutes: int
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    llm_providers: list[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleConfigResponse]
    total: int
