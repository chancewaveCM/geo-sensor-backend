from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.query import QueryStatus


class QueryBase(BaseModel):
    text: str = Field(..., min_length=1, max_length=100000)


class QueryCreate(QueryBase):
    project_id: int


class QueryResponse(QueryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: QueryStatus
    project_id: int
    created_at: datetime
