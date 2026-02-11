"""YouTube publisher for community posts."""

import httpx

from app.services.publishing.base import BasePlatformPublisher, PublishError


class YouTubePublisher(BasePlatformPublisher):
    """Publisher for YouTube Community Posts via YouTube Data API."""

    API_BASE = "https://www.googleapis.com/youtube/v3"

    @property
    def max_length(self) -> int:
        """YouTube community posts support up to 5000 characters."""
        return 5000

    @property
    def supports_media(self) -> bool:
        """YouTube community posts support images and videos."""
        return True

    @property
    def supports_threads(self) -> bool:
        """YouTube community posts don't support threading."""
        return False

    def validate_content(self, content: str) -> list[str]:
        """Validate content length and format."""
        errors = []
        if len(content) > self.max_length:
            errors.append(f"Content exceeds {self.max_length} characters")
        if not content.strip():
            errors.append("Content cannot be empty")
        return errors

    def format_content(self, content: str, options: dict | None = None) -> str:
        """Format content for YouTube (minimal formatting needed)."""
        # YouTube supports basic text formatting
        return content.strip()

    async def publish(self, content: str, token: str, options: dict | None = None) -> dict:
        """
        Publish a community post to YouTube.

        Uses YouTube Data API v3 community posts endpoint.
        """
        errors = self.validate_content(content)
        if errors:
            raise PublishError(f"Validation failed: {', '.join(errors)}")

        formatted = self.format_content(content, options)

        # YouTube Community Posts API endpoint
        # Note: This is a simplified implementation. Real implementation would need:
        # - Channel ID lookup
        # - Proper request body structure
        # - Media upload handling if options include images/videos
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.API_BASE}/communityPosts",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "snippet": {
                            "textMessageDetails": {
                                "messageText": formatted,
                            }
                        }
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    raise PublishError(f"YouTube API error: {response.status_code} {response.text}")

                data = response.json()
                post_id = data.get("id")
                if not post_id:
                    raise PublishError("No post ID returned from YouTube")

                return {
                    "external_id": post_id,
                    "url": f"https://www.youtube.com/post/{post_id}",
                }

            except httpx.HTTPError as e:
                raise PublishError(f"HTTP error publishing to YouTube: {e}")
