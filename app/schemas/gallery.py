"""Pydantic schemas for Gallery operations."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# --- ResponseLabel ---

class ResponseLabelCreate(BaseModel):
    run_response_id: int
    label_type: str = Field(..., pattern="^(flag|quality|category|custom)$")
    label_key: str = Field(..., min_length=1, max_length=100)
    label_value: str | None = None
    severity: str | None = Field(None, pattern="^(info|warning|critical)$")


class ResponseLabelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    run_response_id: int
    label_type: str
    label_key: str
    label_value: str | None = None
    severity: str | None = None
    created_by: int
    resolved_at: datetime | None = None
    resolved_by: int | None = None
    created_at: datetime
    updated_at: datetime


# --- CitationReview ---

class CitationReviewCreate(BaseModel):
    run_citation_id: int
    review_type: str = Field(..., pattern="^(false_positive|false_negative|correct|uncertain)$")
    reviewer_comment: str | None = None


class CitationReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_citation_id: int
    review_type: str
    reviewer_comment: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


# --- Gallery List Item ---

class GalleryRunResponseItem(BaseModel):
    """Gallery card view of a RunResponse."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_run_id: int
    query_version_id: int
    llm_provider: str
    llm_model: str
    content: str | None = None
    word_count: int | None = None
    citation_count: int | None = None
    created_at: datetime
    # Joined fields
    query_text: str | None = None
    run_number: int | None = None
    campaign_name: str | None = None
    label_count: int | None = None
    has_flags: bool = False


class GalleryDetailResponse(BaseModel):
    """Full gallery detail view."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_run_id: int
    query_version_id: int
    llm_provider: str
    llm_model: str
    content: str | None = None
    response_hash: str | None = None
    word_count: int | None = None
    citation_count: int | None = None
    latency_ms: float | None = None
    created_at: datetime
    # Joined
    query_text: str | None = None
    run_number: int | None = None
    campaign_name: str | None = None
    labels: list[ResponseLabelResponse] = []
    citations: list[dict] = []  # RunCitation data


class GalleryFilterParams(BaseModel):
    """Query parameters for gallery filtering."""
    llm_provider: str | None = None
    query_type: str | None = None
    query_id: int | None = None
    cluster_id: int | None = None
    has_flags: bool | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


# --- ComparisonSnapshot ---

class ComparisonSnapshotCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    comparison_type: str = Field(..., pattern="^(llm_vs_llm|date_vs_date|version_vs_version)$")
    config: dict  # Will be JSON serialized
    notes: str | None = None


class ComparisonSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    name: str
    comparison_type: str
    config: str  # JSON string
    notes: str | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime


# --- OperationLog ---

class OperationLogCreate(BaseModel):
    operation_type: str = Field(
        ...,
        pattern="^(promote_to_anchor|anchor_change_request|parser_issue|archive|export|label_action)$",
    )
    target_type: str | None = None
    target_id: int | None = None
    payload: dict | None = None


class OperationLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    operation_type: str
    status: str
    target_type: str | None = None
    target_id: int | None = None
    payload: str | None = None  # JSON string
    created_by: int
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None
    review_comment: str | None = None
    created_at: datetime
    updated_at: datetime


class OperationReviewRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$")
    review_comment: str | None = None
