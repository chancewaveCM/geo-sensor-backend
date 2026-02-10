"""Unified Analysis schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class StartAnalysisRequest(BaseModel):
    """Request to start a unified analysis job."""
    company_profile_id: int
    mode: str = Field(
        default="quick",
        pattern="^(quick|advanced)$",
        description=(
            "Analysis mode: 'quick' (3 categories, 10 queries) or "
            "'advanced' (user-configured)"
        ),
    )
    llm_providers: list[str] = Field(
        default=["gemini", "openai"],
        min_length=1,
        max_length=2,
    )
    # Advanced mode options
    category_count: int | None = Field(default=None, ge=1, le=20)
    queries_per_category: int | None = Field(default=None, ge=1, le=20)


class AnalysisJobResponse(BaseModel):
    """Response for a single analysis job."""
    id: int
    mode: str
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
    error_message: str | None = None

    class Config:
        from_attributes = True


class StartAnalysisResponse(BaseModel):
    """Response after starting an analysis job."""
    job_id: int
    mode: str
    status: str
    message: str
    estimated_queries: int


class AnalysisJobListResponse(BaseModel):
    """List of analysis jobs."""
    jobs: list[AnalysisJobResponse]
    total: int


class DeleteAnalysisResponse(BaseModel):
    """Response after deleting/cancelling an analysis job."""
    job_id: int
    status: str
    message: str


class UpdateQueryRequest(BaseModel):
    """Request to update an expanded query text."""
    text: str = Field(..., min_length=1, max_length=2000)


class RerunQueryRequest(BaseModel):
    """Request to rerun a specific query."""
    llm_providers: list[str] = Field(
        default=["gemini", "openai"],
        min_length=1,
        max_length=2,
    )


class QueryResponse(BaseModel):
    """Response for a single expanded query."""
    id: int
    text: str
    order_index: int
    status: str
    category_id: int

    class Config:
        from_attributes = True


class RerunQueryResponse(BaseModel):
    """Response after rerunning a query."""
    query_id: int
    status: str
    message: str
