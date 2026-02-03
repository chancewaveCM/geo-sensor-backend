from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.response import LLMProvider


class ResponseBase(BaseModel):
    content: str
    llm_provider: LLMProvider
    llm_model: str


class ResponseCreate(ResponseBase):
    query_id: int


class ResponseResponse(ResponseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    query_id: int
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    context_type: str | None = None
    geo_score: float | None = None
    geo_grade: str | None = None
    geo_triggers: dict | None = None
    created_at: datetime
