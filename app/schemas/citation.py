from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.citation import MatchType


class CitationBase(BaseModel):
    matched_text: str
    match_type: MatchType
    confidence: float
    position_start: int
    position_end: int


class CitationCreate(CitationBase):
    brand_id: int
    response_id: int


class CitationResponse(CitationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brand_id: int
    response_id: int
    created_at: datetime
