"""Content Optimizer schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class AnalyzeTextRequest(BaseModel):
    """Request to analyze text content for citation optimization."""
    text: str = Field(..., min_length=50, max_length=50000)
    target_brand: str = Field(..., min_length=1, max_length=255)
    llm_provider: str = Field(default="gemini")


class AnalyzeUrlRequest(BaseModel):
    """Request to analyze a URL's content."""
    url: str = Field(..., max_length=2048)
    target_brand: str = Field(..., min_length=1, max_length=255)
    llm_provider: str = Field(default="gemini")


class DiagnoseRequest(BaseModel):
    """Request for content diagnosis."""
    text: str = Field(..., min_length=50, max_length=50000)
    target_brand: str = Field(..., min_length=1, max_length=255)
    llm_provider: str = Field(default="gemini")


class SuggestRequest(BaseModel):
    """Request for optimization suggestions."""
    text: str = Field(..., min_length=50, max_length=50000)
    target_brand: str = Field(..., min_length=1, max_length=255)
    diagnosis_id: int | None = None
    llm_provider: str = Field(default="gemini")


class CompareRequest(BaseModel):
    """Request to compare original vs optimized content."""
    original_text: str = Field(..., min_length=50, max_length=50000)
    optimized_text: str = Field(..., min_length=50, max_length=50000)
    target_brand: str = Field(..., min_length=1, max_length=255)
    llm_provider: str = Field(default="gemini")


class CitationScore(BaseModel):
    """Citation optimization score breakdown."""
    overall_score: float = Field(..., ge=0, le=100)
    brand_mention_score: float = Field(..., ge=0, le=100)
    authority_score: float = Field(..., ge=0, le=100)
    structure_score: float = Field(..., ge=0, le=100)
    freshness_score: float = Field(..., ge=0, le=100)


class DiagnosisItem(BaseModel):
    """Single diagnosis finding."""
    category: str
    severity: str  # 'critical' | 'warning' | 'info'
    title: str
    description: str
    recommendation: str


class DiagnosisResult(BaseModel):
    """Full diagnosis result."""
    citation_score: CitationScore
    findings: list[DiagnosisItem]
    summary: str


class SuggestionItem(BaseModel):
    """Single optimization suggestion."""
    category: str
    priority: str  # 'high' | 'medium' | 'low'
    title: str
    description: str
    example_before: str | None = None
    example_after: str | None = None


class SuggestResult(BaseModel):
    """Optimization suggestions result."""
    suggestions: list[SuggestionItem]
    estimated_score_improvement: float
    summary: str


class CompareResult(BaseModel):
    """Comparison between original and optimized content."""
    original_score: CitationScore
    optimized_score: CitationScore
    improvement: float
    changes_summary: list[str]


class AnalysisHistoryItem(BaseModel):
    """History entry for content analysis."""
    id: int
    target_brand: str
    overall_score: float
    text_preview: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisHistoryResponse(BaseModel):
    """List of analysis history entries."""
    items: list[AnalysisHistoryItem]
    total: int
