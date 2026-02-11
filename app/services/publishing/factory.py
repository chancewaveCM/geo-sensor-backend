"""Factory for creating platform publishers."""

from app.models.oauth_token import OAuthPlatform
from app.services.publishing.base import BasePlatformPublisher, PublishError
from app.services.publishing.instagram import InstagramPublisher
from app.services.publishing.linkedin import LinkedInPublisher
from app.services.publishing.twitter import TwitterPublisher
from app.services.publishing.youtube import YouTubePublisher


def get_publisher(platform: str) -> BasePlatformPublisher:
    """
    Get the appropriate publisher for a platform.

    Args:
        platform: Platform identifier

    Returns:
        Platform publisher instance

    Raises:
        PublishError: If platform is not supported
    """
    publishers = {
        OAuthPlatform.YOUTUBE.value: YouTubePublisher,
        OAuthPlatform.INSTAGRAM.value: InstagramPublisher,
        OAuthPlatform.LINKEDIN.value: LinkedInPublisher,
        OAuthPlatform.TWITTER.value: TwitterPublisher,
    }

    publisher_class = publishers.get(platform)
    if not publisher_class:
        raise PublishError(f"Unsupported platform: {platform}")

    return publisher_class()
