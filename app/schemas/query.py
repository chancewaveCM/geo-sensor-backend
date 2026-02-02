from pydantic import BaseModel, ConfigDict
from datetime import datetime
from app.models.query import QueryStatus


class QueryBase(BaseModel):
    text: str


class QueryCreate(QueryBase):
    project_id: int


class QueryResponse(QueryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: QueryStatus
    project_id: int
    created_at: datetime
