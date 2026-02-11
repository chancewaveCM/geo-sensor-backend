"""OAuth schemas for platform integration."""

from datetime import datetime

from pydantic import BaseModel, Field


class OAuthPlatformStatus(BaseModel):
    """OAuth platform connection status."""

    platform: str = Field(
        ..., description="Platform identifier (youtube/instagram/linkedin/twitter)"
    )
    is_connected: bool = Field(..., description="Whether platform is connected")
    connected_at: datetime | None = Field(None, description="When platform was connected")
    scopes: list[str] | None = Field(None, description="Granted OAuth scopes")


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request data."""

    code: str = Field(..., description="Authorization code from OAuth provider")
    state: str = Field(..., description="State parameter for CSRF protection")
    redirect_uri: str = Field(..., description="Redirect URI used in authorization request")


class OAuthConnectResponse(BaseModel):
    """OAuth connection initiation response."""

    auth_url: str = Field(..., description="Authorization URL to redirect user to")
    state: str = Field(..., description="State parameter for CSRF protection")


class OAuthTokenResponse(BaseModel):
    """OAuth token operation response."""

    platform: str = Field(..., description="Platform identifier")
    connected: bool = Field(..., description="Whether platform is now connected")
    expires_at: datetime | None = Field(None, description="Token expiration time")


class OAuthStatusResponse(BaseModel):
    """OAuth status for all platforms."""

    platforms: list[OAuthPlatformStatus] = Field(..., description="Status for all platforms")
