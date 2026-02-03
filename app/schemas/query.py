from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import MAX_QUERY_TEXT_LENGTH, MIN_STRING_LENGTH
from app.models.query import QueryStatus
from app.schemas.base import BaseResponseSchema


class QueryBase(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)


class QueryCreate(QueryBase):
    text: str = Field(
        ..., min_length=MIN_STRING_LENGTH, max_length=MAX_QUERY_TEXT_LENGTH
    )
    project_id: int = Field(..., gt=0)


class QueryResponse(QueryBase, BaseResponseSchema):
    id: int
    status: QueryStatus
    project_id: int
    created_at: datetime
