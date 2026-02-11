"""Publishing schemas for SNS publishing."""

from datetime import datetime

from pydantic import BaseModel, Field


class PublishRequest(BaseModel):
    """Request to publish content to a platform."""

    content: str = Field(..., min_length=1, max_length=10000)
    platform: str = Field(..., pattern="^(youtube|instagram|linkedin|twitter)$")
    scheduled_at: datetime | None = Field(None, description="Schedule for future publication")
    format_options: dict | None = Field(None, description="Platform-specific formatting options")


class PublicationResponse(BaseModel):
    """Response with publication details."""

    id: int
    content: str
    platform: str
    status: str
    published_at: datetime | None
    external_id: str | None
    error_message: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class PublicationListResponse(BaseModel):
    """Response with list of publications."""

    publications: list[PublicationResponse]
    total: int


class PlatformFormatInfo(BaseModel):
    """Information about platform content format restrictions."""

    platform: str
    max_length: int
    supports_media: bool
    supports_threads: bool
