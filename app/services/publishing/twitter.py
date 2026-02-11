"""Twitter publisher for tweets."""

import httpx

from app.services.publishing.base import BasePlatformPublisher, PublishError


class TwitterPublisher(BasePlatformPublisher):
    """Publisher for Twitter tweets via Twitter API v2."""

    API_BASE = "https://api.twitter.com/2"

    @property
    def max_length(self) -> int:
        """Twitter supports up to 280 characters (or 4000 for Twitter Blue)."""
        return 280

    @property
    def supports_media(self) -> bool:
        """Twitter supports images, videos, and GIFs."""
        return True

    @property
    def supports_threads(self) -> bool:
        """Twitter supports threaded tweets."""
        return True

    def validate_content(self, content: str) -> list[str]:
        """Validate content length."""
        errors = []
        if len(content) > self.max_length:
            errors.append(f"Content exceeds {self.max_length} characters")
        if not content.strip():
            errors.append("Content cannot be empty")
        return errors

    def format_content(self, content: str, options: dict | None = None) -> str:
        """Format content for Twitter."""
        return content.strip()

    async def publish(self, content: str, token: str, options: dict | None = None) -> dict:
        """
        Publish a tweet to Twitter.

        Uses Twitter API v2 tweets endpoint.
        """
        errors = self.validate_content(content)
        if errors:
            raise PublishError(f"Validation failed: {', '.join(errors)}")

        formatted = self.format_content(content, options)

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.API_BASE}/tweets",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={"text": formatted},
                    timeout=30.0,
                )

                if response.status_code not in (200, 201):
                    raise PublishError(f"Twitter API error: {response.status_code} {response.text}")

                data = response.json()
                tweet_data = data.get("data", {})
                tweet_id = tweet_data.get("id")
                if not tweet_id:
                    raise PublishError("No tweet ID returned from Twitter")

                return {
                    "external_id": tweet_id,
                    "url": f"https://twitter.com/i/web/status/{tweet_id}",
                }

            except httpx.HTTPError as e:
                raise PublishError(f"HTTP error publishing to Twitter: {e}")
