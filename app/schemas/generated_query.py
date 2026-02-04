"""Generated Query schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.generated_query import GeneratedQueryStatus, QueryCategory


class GeneratedQueryBase(BaseModel):
    text: str
    order_index: int = Field(..., ge=1, le=30)
    category: QueryCategory
    is_selected: bool = True


class GeneratedQueryCreate(GeneratedQueryBase):
    company_profile_id: int


class GeneratedQueryUpdate(BaseModel):
    text: str | None = None
    is_selected: bool | None = None
    status: GeneratedQueryStatus | None = None


class GeneratedQueryResponse(GeneratedQueryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: GeneratedQueryStatus
    original_text: str | None
    company_profile_id: int
    created_at: datetime
    updated_at: datetime


class GenerateQueriesRequest(BaseModel):
    company_profile_id: int


class BulkUpdateRequest(BaseModel):
    query_ids: list[int]
    is_selected: bool | None = None
    status: GeneratedQueryStatus | None = None
