"""Content Rewrite schemas for AI-powered content optimization."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RewriteRequest(BaseModel):
    """Request to generate content rewrite variants."""

    original_content: str = Field(..., min_length=1, max_length=10000)
    suggestions: list[str] = Field(default_factory=list, max_length=20)
    brand_voice: str | None = Field(None, max_length=500)
    llm_provider: str = Field(default="openai")
    num_variants: int = Field(default=3, ge=1, le=5)


class RewriteVariantResponse(BaseModel):
    """Response model for a rewrite variant."""

    id: int
    variant_number: int
    content: str
    status: str
    diff_summary: str

    class Config:
        from_attributes = True


class RewriteResponse(BaseModel):
    """Response model for a content rewrite with variants."""

    id: int
    original_content: str
    variants: list[RewriteVariantResponse]
    created_at: datetime

    class Config:
        from_attributes = True


class VariantApprovalRequest(BaseModel):
    """Request to approve or reject a variant."""

    status: Literal["approved", "rejected"]


class RewriteListResponse(BaseModel):
    """Response model for paginated list of rewrites."""

    rewrites: list[RewriteResponse]
    total: int
