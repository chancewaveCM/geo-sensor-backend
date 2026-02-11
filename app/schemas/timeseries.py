"""Schemas for time-series analytics and competitive benchmarking."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Time-Series (P1-S2)
# ---------------------------------------------------------------------------


class EnhancedTimeseriesDataPoint(BaseModel):
    """Single data point in an enhanced timeseries."""

    date: datetime
    citation_share: float
    citation_count: int
    response_count: int


class TrendSummary(BaseModel):
    """Trend summary for a brand over a given period."""

    direction: str  # "up" | "down" | "flat"
    change_percent: float
    change_absolute: float
    period: str  # "week" | "month" | "run"


class BrandTrend(BaseModel):
    """Trend information for a single brand."""

    brand_name: str
    current_share: float
    trend: TrendSummary
    data_points: list[EnhancedTimeseriesDataPoint]


class EnhancedTimeseriesResponse(BaseModel):
    """Enhanced timeseries response with per-brand trends."""

    campaign_id: int
    granularity: str  # "daily" | "weekly" | "monthly"
    date_from: datetime
    date_to: datetime
    brands: list[BrandTrend]


class TrendsSummaryResponse(BaseModel):
    """Collection of per-brand trend summaries."""

    campaign_id: int
    brands: list[BrandTrend]


# ---------------------------------------------------------------------------
# Annotations
# ---------------------------------------------------------------------------


class AnnotationCreate(BaseModel):
    """Create a timeseries annotation."""

    date: datetime
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    annotation_type: str = Field(
        default="manual", pattern="^(manual|query_change|model_change)$"
    )


class AnnotationResponse(BaseModel):
    """Annotation response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    date: datetime
    title: str
    description: str | None = None
    annotation_type: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Competitive Benchmarking (P1-S3)
# ---------------------------------------------------------------------------


class CompetitiveBrandEntry(BaseModel):
    """A single brand in the competitive overview."""

    brand_name: str
    is_target: bool
    citation_share: float
    citation_count: int
    rank: int
    change_from_previous: float | None = None  # vs previous period


class CompetitiveOverviewResponse(BaseModel):
    """Competitive overview — citation share matrix."""

    campaign_id: int
    period: str
    brands: list[CompetitiveBrandEntry]
    total_responses: int


class CompetitiveTrendEntry(BaseModel):
    """Single entry in competitive trend data."""

    date: datetime
    brand_name: str
    citation_share: float


class CompetitiveTrendsResponse(BaseModel):
    """Brand trajectories over time."""

    campaign_id: int
    date_from: datetime
    date_to: datetime
    entries: list[CompetitiveTrendEntry]


class CompetitiveAlert(BaseModel):
    """Alert when a brand's share changes significantly."""

    brand_name: str
    change_percent: float
    direction: str  # "up" | "down"
    period: str
    severity: str  # "info" | "warning" | "critical"


class CompetitiveAlertsResponse(BaseModel):
    """Collection of competitive alerts."""

    campaign_id: int
    alerts: list[CompetitiveAlert]
