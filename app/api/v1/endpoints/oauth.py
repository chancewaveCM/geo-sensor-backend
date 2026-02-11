"""OAuth endpoints for platform integrations."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import WorkspaceAdminDep, get_db
from app.models.oauth_token import OAuthPlatform
from app.schemas.oauth import (
    OAuthCallbackRequest,
    OAuthConnectResponse,
    OAuthStatusResponse,
    OAuthTokenResponse,
)
from app.services.oauth import OAuthService
from app.services.oauth.oauth_service import OAuthError

router = APIRouter(prefix="/workspaces/{workspace_id}/oauth", tags=["oauth"])

# SSRF protection: allowed redirect URI origins
ALLOWED_REDIRECT_ORIGINS = [
    "http://localhost:3765",
    "http://localhost:3000",
    "https://geosensor.io",
]


def validate_redirect_uri(redirect_uri: str) -> None:
    """Validate redirect URI against allowed origins (SSRF protection)."""
    if not any(redirect_uri.startswith(origin) for origin in ALLOWED_REDIRECT_ORIGINS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid redirect_uri. Must start with one of: {ALLOWED_REDIRECT_ORIGINS}",
        )


@router.get("/status", response_model=OAuthStatusResponse)
async def get_oauth_status(
    workspace_id: int,
    admin: WorkspaceAdminDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OAuthStatusResponse:
    """Get OAuth connection status for all platforms."""
    service = OAuthService()
    platforms = await service.get_status(workspace_id, db)
    return OAuthStatusResponse(platforms=platforms)


@router.post("/{platform}/connect", response_model=OAuthConnectResponse)
async def initiate_oauth_flow(
    workspace_id: int,
    platform: str,
    redirect_uri: str,
    admin: WorkspaceAdminDep,
) -> OAuthConnectResponse:
    """
    Initiate OAuth flow for a platform.

    Returns authorization URL to redirect user to.
    """
    # Validate platform
    try:
        OAuthPlatform(platform)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform: {platform}",
        ) from e

    # SSRF protection
    validate_redirect_uri(redirect_uri)

    # Generate auth URL
    service = OAuthService()
    try:
        result = service.get_auth_url(platform, redirect_uri, workspace_id)
        return OAuthConnectResponse(auth_url=result["auth_url"], state=result["state"])
    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.post("/{platform}/callback", response_model=OAuthTokenResponse)
async def handle_oauth_callback(
    workspace_id: int,
    platform: str,
    request: OAuthCallbackRequest,
    admin: WorkspaceAdminDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OAuthTokenResponse:
    """
    Handle OAuth callback and exchange authorization code for tokens.
    """
    # Validate platform
    try:
        OAuthPlatform(platform)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform: {platform}",
        ) from e

    # SSRF protection
    validate_redirect_uri(request.redirect_uri)

    # Verify state contains correct workspace_id
    try:
        state_data = json.loads(request.state)
        if state_data.get("workspace_id") != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state: workspace_id mismatch",
            )
    except (json.JSONDecodeError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid state parameter",
        ) from e

    # Handle callback
    service = OAuthService()
    try:
        token = await service.handle_callback(
            platform, request.code, request.state, request.redirect_uri, workspace_id, db
        )
        return OAuthTokenResponse(
            platform=token.platform,
            connected=True,
            expires_at=token.expires_at,
        )
    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.post("/{platform}/refresh", response_model=OAuthTokenResponse)
async def refresh_oauth_token(
    workspace_id: int,
    platform: str,
    admin: WorkspaceAdminDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OAuthTokenResponse:
    """
    Manually refresh an OAuth token.
    """
    # Validate platform
    try:
        OAuthPlatform(platform)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform: {platform}",
        ) from e

    # Refresh token
    service = OAuthService()
    try:
        token = await service.refresh_token(platform, workspace_id, db)
        return OAuthTokenResponse(
            platform=token.platform,
            connected=True,
            expires_at=token.expires_at,
        )
    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e


@router.delete("/{platform}/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_oauth_token(
    workspace_id: int,
    platform: str,
    admin: WorkspaceAdminDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Revoke and delete OAuth token for a platform.
    """
    # Validate platform
    try:
        OAuthPlatform(platform)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid platform: {platform}",
        ) from e

    # Revoke token
    service = OAuthService()
    try:
        await service.revoke_token(platform, workspace_id, db)
    except OAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        ) from e
