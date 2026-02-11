"""Base class for platform publishers."""

from abc import ABC, abstractmethod


class PublishError(Exception):
    """Raised when publishing fails."""

    pass


class BasePlatformPublisher(ABC):
    """Abstract base class for platform publishers."""

    @abstractmethod
    async def publish(self, content: str, token: str, options: dict | None = None) -> dict:
        """
        Publish content to the platform.

        Args:
            content: Content to publish
            token: OAuth access token
            options: Platform-specific formatting options

        Returns:
            Dict with external_id and url of published content

        Raises:
            PublishError: If publishing fails
        """
        pass

    @abstractmethod
    def validate_content(self, content: str) -> list[str]:
        """
        Validate content against platform restrictions.

        Args:
            content: Content to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        pass

    @abstractmethod
    def format_content(self, content: str, options: dict | None = None) -> str:
        """
        Format content according to platform requirements.

        Args:
            content: Raw content
            options: Platform-specific formatting options

        Returns:
            Formatted content
        """
        pass

    @property
    @abstractmethod
    def max_length(self) -> int:
        """Maximum content length for this platform."""
        pass

    @property
    @abstractmethod
    def supports_media(self) -> bool:
        """Whether this platform supports media attachments."""
        pass

    @property
    @abstractmethod
    def supports_threads(self) -> bool:
        """Whether this platform supports threaded posts."""
        pass
