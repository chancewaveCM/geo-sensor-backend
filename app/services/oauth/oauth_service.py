"""OAuth service for managing platform integrations."""

import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.encryption import decrypt_token, encrypt_token
from app.models.oauth_token import OAuthPlatform, OAuthToken
from app.schemas.oauth import OAuthPlatformStatus


class OAuthError(Exception):
    """Raised when OAuth operations fail."""

    pass


class OAuthService:
    """Service for managing OAuth platform integrations."""

    # Platform configurations
    PLATFORM_CONFIGS = {
        OAuthPlatform.YOUTUBE.value: {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": [
                "https://www.googleapis.com/auth/youtube.readonly",
                "https://www.googleapis.com/auth/youtube.upload",
            ],
        },
        OAuthPlatform.INSTAGRAM.value: {
            "auth_url": "https://api.instagram.com/oauth/authorize",
            "token_url": "https://api.instagram.com/oauth/access_token",
            "scopes": ["user_profile", "user_media"],
        },
        OAuthPlatform.LINKEDIN.value: {
            "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
            "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
            "scopes": ["r_liteprofile", "w_member_social"],
        },
        OAuthPlatform.TWITTER.value: {
            "auth_url": "https://twitter.com/i/oauth2/authorize",
            "token_url": "https://api.twitter.com/2/oauth2/token",
            "scopes": ["tweet.read", "tweet.write", "users.read"],
        },
    }

    def _get_platform_config(self, platform: str) -> dict[str, Any]:
        """Get configuration for a platform."""
        if platform not in self.PLATFORM_CONFIGS:
            raise OAuthError(f"Unsupported platform: {platform}")
        return self.PLATFORM_CONFIGS[platform]

    def _get_client_credentials(self, platform: str) -> tuple[str, str]:
        """Get client ID and secret for a platform."""
        credentials_map = {
            OAuthPlatform.YOUTUBE.value: (
                settings.YOUTUBE_CLIENT_ID,
                settings.YOUTUBE_CLIENT_SECRET,
            ),
            OAuthPlatform.INSTAGRAM.value: (
                settings.INSTAGRAM_CLIENT_ID,
                settings.INSTAGRAM_CLIENT_SECRET,
            ),
            OAuthPlatform.LINKEDIN.value: (
                settings.LINKEDIN_CLIENT_ID,
                settings.LINKEDIN_CLIENT_SECRET,
            ),
            OAuthPlatform.TWITTER.value: (
                settings.TWITTER_CLIENT_ID,
                settings.TWITTER_CLIENT_SECRET,
            ),
        }

        if platform not in credentials_map:
            raise OAuthError(f"No credentials configured for platform: {platform}")

        client_id, client_secret = credentials_map[platform]
        if not client_id or not client_secret:
            raise OAuthError(f"Missing credentials for platform: {platform}")

        return client_id, client_secret

    def get_auth_url(self, platform: str, redirect_uri: str, workspace_id: int) -> dict[str, str]:
        """
        Generate OAuth authorization URL.

        Args:
            platform: Platform identifier
            redirect_uri: Callback URL
            workspace_id: Workspace ID (included in state)

        Returns:
            Dict with auth_url and state
        """
        config = self._get_platform_config(platform)
        client_id, _ = self._get_client_credentials(platform)

        # Generate state with workspace_id for CSRF protection
        state = secrets.token_urlsafe(32)
        state_data = {"state": state, "workspace_id": workspace_id}
        state_param = json.dumps(state_data)

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(config["scopes"]),
            "state": state_param,
            "access_type": "offline",  # Request refresh token
            "prompt": "consent",  # Force consent screen to get refresh token
        }

        auth_url = f"{config['auth_url']}?{urlencode(params)}"
        return {"auth_url": auth_url, "state": state}

    async def handle_callback(
        self,
        platform: str,
        code: str,
        state: str,
        redirect_uri: str,
        workspace_id: int,
        db: AsyncSession,
    ) -> OAuthToken:
        """
        Handle OAuth callback and exchange code for tokens.

        Args:
            platform: Platform identifier
            code: Authorization code
            state: State parameter (for verification)
            redirect_uri: Redirect URI used in auth request
            workspace_id: Workspace ID
            db: Database session

        Returns:
            Created/updated OAuthToken
        """
        config = self._get_platform_config(platform)
        client_id, client_secret = self._get_client_credentials(platform)

        # Exchange code for tokens
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["token_url"],
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise OAuthError(
                    f"Token exchange failed: {response.status_code} {response.text}"
                )

            token_data = response.json()

        # Extract token information
        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in")
        token_type = token_data.get("token_type", "Bearer")
        scope = token_data.get("scope", "")

        if not access_token:
            raise OAuthError("No access token received from provider")

        # Calculate expiration
        expires_at = None
        if expires_in:
            expires_at = datetime.now(tz=UTC) + timedelta(seconds=int(expires_in))

        # Encrypt tokens
        encrypted_access = encrypt_token(access_token)
        encrypted_refresh = encrypt_token(refresh_token) if refresh_token else None

        # Store or update token
        stmt = select(OAuthToken).where(
            OAuthToken.workspace_id == workspace_id, OAuthToken.platform == platform
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.access_token = encrypted_access
            existing.refresh_token = encrypted_refresh
            existing.token_type = token_type
            existing.expires_at = expires_at
            existing.scopes = scope
            oauth_token = existing
        else:
            oauth_token = OAuthToken(
                workspace_id=workspace_id,
                platform=platform,
                access_token=encrypted_access,
                refresh_token=encrypted_refresh,
                token_type=token_type,
                expires_at=expires_at,
                scopes=scope,
            )
            db.add(oauth_token)

        await db.commit()
        await db.refresh(oauth_token)
        return oauth_token

    async def refresh_token(
        self, platform: str, workspace_id: int, db: AsyncSession
    ) -> OAuthToken:
        """
        Refresh an expired OAuth token.

        Args:
            platform: Platform identifier
            workspace_id: Workspace ID
            db: Database session

        Returns:
            Updated OAuthToken
        """
        # Get existing token
        stmt = select(OAuthToken).where(
            OAuthToken.workspace_id == workspace_id, OAuthToken.platform == platform
        )
        result = await db.execute(stmt)
        oauth_token = result.scalar_one_or_none()

        if not oauth_token:
            raise OAuthError(f"No token found for platform: {platform}")

        if not oauth_token.refresh_token:
            raise OAuthError(f"No refresh token available for platform: {platform}")

        # Decrypt refresh token
        refresh_token_plain = decrypt_token(oauth_token.refresh_token)

        config = self._get_platform_config(platform)
        client_id, client_secret = self._get_client_credentials(platform)

        # Request new access token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config["token_url"],
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token_plain,
                    "grant_type": "refresh_token",
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                raise OAuthError(f"Token refresh failed: {response.status_code} {response.text}")

            token_data = response.json()

        # Update token
        access_token = token_data.get("access_token")
        if not access_token:
            raise OAuthError("No access token received from refresh")

        expires_in = token_data.get("expires_in")
        expires_at = None
        if expires_in:
            expires_at = datetime.now(tz=UTC) + timedelta(seconds=int(expires_in))

        oauth_token.access_token = encrypt_token(access_token)
        oauth_token.expires_at = expires_at

        # Update refresh token if new one provided
        new_refresh = token_data.get("refresh_token")
        if new_refresh:
            oauth_token.refresh_token = encrypt_token(new_refresh)

        await db.commit()
        await db.refresh(oauth_token)
        return oauth_token

    async def revoke_token(
        self, platform: str, workspace_id: int, db: AsyncSession
    ) -> None:
        """
        Revoke and delete OAuth token.

        Args:
            platform: Platform identifier
            workspace_id: Workspace ID
            db: Database session
        """
        stmt = select(OAuthToken).where(
            OAuthToken.workspace_id == workspace_id, OAuthToken.platform == platform
        )
        result = await db.execute(stmt)
        oauth_token = result.scalar_one_or_none()

        if oauth_token:
            await db.delete(oauth_token)
            await db.commit()

    async def get_status(
        self, workspace_id: int, db: AsyncSession
    ) -> list[OAuthPlatformStatus]:
        """
        Get connection status for all platforms.

        Args:
            workspace_id: Workspace ID
            db: Database session

        Returns:
            List of platform status objects
        """
        stmt = select(OAuthToken).where(OAuthToken.workspace_id == workspace_id)
        result = await db.execute(stmt)
        tokens = result.scalars().all()

        # Create status map
        token_map = {token.platform: token for token in tokens}

        statuses = []
        for platform in OAuthPlatform:
            token = token_map.get(platform.value)
            if token:
                scopes = token.scopes.split() if token.scopes else None
                statuses.append(
                    OAuthPlatformStatus(
                        platform=platform.value,
                        is_connected=True,
                        connected_at=token.created_at,
                        scopes=scopes,
                    )
                )
            else:
                statuses.append(
                    OAuthPlatformStatus(
                        platform=platform.value,
                        is_connected=False,
                        connected_at=None,
                        scopes=None,
                    )
                )

        return statuses

    async def get_valid_token(
        self, platform: str, workspace_id: int, db: AsyncSession
    ) -> str:
        """
        Get a valid access token, refreshing if expired.

        Args:
            platform: Platform identifier
            workspace_id: Workspace ID
            db: Database session

        Returns:
            Decrypted access token

        Raises:
            OAuthError: If no token exists or refresh fails
        """
        stmt = select(OAuthToken).where(
            OAuthToken.workspace_id == workspace_id, OAuthToken.platform == platform
        )
        result = await db.execute(stmt)
        oauth_token = result.scalar_one_or_none()

        if not oauth_token:
            raise OAuthError(f"No token found for platform: {platform}")

        # Check if token is expired
        if oauth_token.expires_at and oauth_token.expires_at <= datetime.now(tz=UTC):
            # Refresh token
            oauth_token = await self.refresh_token(platform, workspace_id, db)

        # Decrypt and return access token
        return decrypt_token(oauth_token.access_token)
