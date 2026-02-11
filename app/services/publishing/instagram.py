"""Instagram publisher for posts."""

import httpx

from app.services.publishing.base import BasePlatformPublisher, PublishError


class InstagramPublisher(BasePlatformPublisher):
    """Publisher for Instagram posts via Instagram Graph API."""

    API_BASE = "https://graph.instagram.com"

    @property
    def max_length(self) -> int:
        """Instagram captions support up to 2200 characters."""
        return 2200

    @property
    def supports_media(self) -> bool:
        """Instagram requires media (images or videos) for posts."""
        return True

    @property
    def supports_threads(self) -> bool:
        """Instagram supports carousel posts."""
        return True

    def validate_content(self, content: str) -> list[str]:
        """Validate content length."""
        errors = []
        if len(content) > self.max_length:
            errors.append(f"Content exceeds {self.max_length} characters")
        # Note: Instagram posts require media, but we allow text-only
        # for cases where media will be added later
        return errors

    def format_content(self, content: str, options: dict | None = None) -> str:
        """Format content for Instagram."""
        return content.strip()

    async def publish(self, content: str, token: str, options: dict | None = None) -> dict:
        """
        Publish a post to Instagram.

        Uses Instagram Graph API. Note: Instagram requires media for posts,
        so this implementation creates a text-only caption that would need
        to be paired with media in production use.
        """
        errors = self.validate_content(content)
        if errors:
            raise PublishError(f"Validation failed: {', '.join(errors)}")

        formatted = self.format_content(content, options)

        # Get Instagram Business Account ID
        async with httpx.AsyncClient() as client:
            try:
                # First get the user's Instagram Business Account
                me_response = await client.get(
                    f"{self.API_BASE}/me",
                    params={
                        "fields": "id,username",
                        "access_token": token,
                    },
                    timeout=30.0,
                )

                if me_response.status_code != 200:
                    raise PublishError(f"Instagram me API error: {me_response.status_code}")

                me_data = me_response.json()
                ig_user_id = me_data.get("id")
                if not ig_user_id:
                    raise PublishError("Could not retrieve Instagram user ID")

                # For a real implementation, this would:
                # 1. Upload media to a container
                # 2. Create a media object with the caption
                # 3. Publish the media object
                #
                # Simplified version for text-only (will fail without media):
                container_response = await client.post(
                    f"{self.API_BASE}/{ig_user_id}/media",
                    params={
                        "caption": formatted,
                        "access_token": token,
                    },
                    timeout=30.0,
                )

                if container_response.status_code not in (200, 201):
                    raise PublishError(
                        f"Instagram container API error: "
                        f"{container_response.status_code} {container_response.text}"
                    )

                container_data = container_response.json()
                container_id = container_data.get("id")
                if not container_id:
                    raise PublishError("No container ID returned from Instagram")

                # Publish the container
                publish_response = await client.post(
                    f"{self.API_BASE}/{ig_user_id}/media_publish",
                    params={
                        "creation_id": container_id,
                        "access_token": token,
                    },
                    timeout=30.0,
                )

                if publish_response.status_code not in (200, 201):
                    raise PublishError(
                        f"Instagram publish API error: "
                        f"{publish_response.status_code} {publish_response.text}"
                    )

                publish_data = publish_response.json()
                media_id = publish_data.get("id")
                if not media_id:
                    raise PublishError("No media ID returned from Instagram")

                return {
                    "external_id": media_id,
                    "url": f"https://www.instagram.com/p/{media_id}",
                }

            except httpx.HTTPError as e:
                raise PublishError(f"HTTP error publishing to Instagram: {e}")
