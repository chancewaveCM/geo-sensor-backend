"""
LLM Service Factory
"""


from .base import BaseLLMService, LLMProvider
from .gemini import GeminiService
from .openai_provider import OpenAIService


class LLMFactory:
    """Factory for creating LLM service instances"""

    _instances: dict[str, BaseLLMService] = {}

    @classmethod
    def create(
        cls,
        provider: LLMProvider,
        api_key: str,
        model: str | None = None,
        cache: bool = True,
    ) -> BaseLLMService:
        """
        Create or get cached LLM service instance

        Args:
            provider: LLM provider type
            api_key: API key for the provider
            model: Optional model override
            cache: Whether to cache and reuse instances

        Returns:
            BaseLLMService instance
        """
        cache_key = f"{provider.value}:{model or 'default'}"

        if cache and cache_key in cls._instances:
            return cls._instances[cache_key]

        if provider == LLMProvider.GEMINI:
            instance = GeminiService(api_key, model or "gemini-2.5-flash")
        elif provider == LLMProvider.OPENAI:
            instance = OpenAIService(api_key, model or "gpt-5-nano")
        else:
            raise ValueError(f"Unknown provider: {provider}")

        if cache:
            cls._instances[cache_key] = instance

        return instance

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached instances"""
        cls._instances.clear()
