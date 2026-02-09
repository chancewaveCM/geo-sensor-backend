"""Dashboard response schemas for aggregate APIs."""

from pydantic import BaseModel


class CitationShareResponse(BaseModel):
    """Citation share aggregation for a pipeline job."""

    total_citation_share: float
    by_provider: dict[str, float]  # {"gemini": 45.2, "openai": 38.1}
    total_queries: int
    total_citations: int

    class Config:
        from_attributes = True


class CitationTrendItem(BaseModel):
    """Single time-series data point for citation trends."""

    date: str  # ISO date (YYYY-MM-DD)
    citation_share: float
    provider: str | None = None

    class Config:
        from_attributes = True


class CitationTrendResponse(BaseModel):
    """Time-series citation trend data."""

    items: list[CitationTrendItem]

    class Config:
        from_attributes = True


class BrandRankingItem(BaseModel):
    """Brand ranking with citation metrics."""

    brand: str
    citation_count: int
    citation_share: float
    avg_position: float | None = None
    is_target: bool = False

    class Config:
        from_attributes = True


class BrandRankingResponse(BaseModel):
    """Brand ranking list with citation metrics."""

    brands: list[BrandRankingItem]
    total_citations: int

    class Config:
        from_attributes = True


class GeoScoreSummaryItem(BaseModel):
    """Single GEO trigger score."""

    trigger: str
    score: float
    description: str | None = None

    class Config:
        from_attributes = True


class GeoScoreSummaryResponse(BaseModel):
    """GEO 5-trigger summary with overall score."""

    overall_score: float
    triggers: list[GeoScoreSummaryItem]

    class Config:
        from_attributes = True
