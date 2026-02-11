"""LinkedIn publisher for text posts."""

import httpx

from app.services.publishing.base import BasePlatformPublisher, PublishError


class LinkedInPublisher(BasePlatformPublisher):
    """Publisher for LinkedIn posts via LinkedIn API."""

    API_BASE = "https://api.linkedin.com/v2"

    @property
    def max_length(self) -> int:
        """LinkedIn posts support up to 3000 characters."""
        return 3000

    @property
    def supports_media(self) -> bool:
        """LinkedIn posts support images and documents."""
        return True

    @property
    def supports_threads(self) -> bool:
        """LinkedIn doesn't support threading."""
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
        """Format content for LinkedIn."""
        return content.strip()

    async def publish(self, content: str, token: str, options: dict | None = None) -> dict:
        """
        Publish a post to LinkedIn.

        Uses LinkedIn API v2 UGC (User Generated Content) posts.
        """
        errors = self.validate_content(content)
        if errors:
            raise PublishError(f"Validation failed: {', '.join(errors)}")

        formatted = self.format_content(content, options)

        # First, get the user's profile ID
        async with httpx.AsyncClient() as client:
            try:
                # Get user profile
                profile_response = await client.get(
                    f"{self.API_BASE}/me",
                    headers={
                        "Authorization": f"Bearer {token}",
                    },
                    timeout=30.0,
                )

                if profile_response.status_code != 200:
                    raise PublishError(
                        f"LinkedIn profile API error: {profile_response.status_code}"
                    )

                profile_data = profile_response.json()
                author_id = profile_data.get("id")
                if not author_id:
                    raise PublishError("Could not retrieve LinkedIn profile ID")

                # Create UGC post
                ugc_response = await client.post(
                    f"{self.API_BASE}/ugcPosts",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0",
                    },
                    json={
                        "author": f"urn:li:person:{author_id}",
                        "lifecycleState": "PUBLISHED",
                        "specificContent": {
                            "com.linkedin.ugc.ShareContent": {
                                "shareCommentary": {"text": formatted},
                                "shareMediaCategory": "NONE",
                            }
                        },
                        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
                    },
                    timeout=30.0,
                )

                if ugc_response.status_code not in (200, 201):
                    raise PublishError(
                        f"LinkedIn UGC API error: {ugc_response.status_code} {ugc_response.text}"
                    )

                data = ugc_response.json()
                post_id = data.get("id")
                if not post_id:
                    raise PublishError("No post ID returned from LinkedIn")

                return {
                    "external_id": post_id,
                    "url": f"https://www.linkedin.com/feed/update/{post_id}",
                }

            except httpx.HTTPError as e:
                raise PublishError(f"HTTP error publishing to LinkedIn: {e}")
