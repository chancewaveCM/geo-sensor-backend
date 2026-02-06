"""
Multi-LLM Query Service
F4: Parallel LLM querying with fallback support
"""

import asyncio
import logging
import time
from dataclasses import dataclass

from app.core.config import settings

from .base import LLMProvider, LLMResponse
from .factory import LLMFactory

logger = logging.getLogger(__name__)


@dataclass
class MultiLLMResponse:
    """Aggregated response from multiple LLM providers"""

    responses: dict[LLMProvider, LLMResponse]  # provider -> response
    errors: dict[LLMProvider, str]  # provider -> error message
    total_latency_ms: float
    successful_count: int

    @property
    def all_content(self) -> dict[str, str]:
        """Get content from all successful responses"""
        return {p.value: r.content for p, r in self.responses.items()}


class MultiLLMService:
    """Service to query multiple LLMs simultaneously"""

    def __init__(self):
        """Initialize multi-LLM service with available providers"""
        self._provider_configs = {
            LLMProvider.GEMINI: {
                "api_key": settings.GEMINI_API_KEY,
                "model": settings.GEMINI_MODEL,
            },
            LLMProvider.OPENAI: {
                "api_key": settings.OPENAI_API_KEY,
                "model": settings.OPENAI_MODEL,
            },
        }

    def _get_available_providers(
        self, requested_providers: list[LLMProvider] | None = None
    ) -> list[LLMProvider]:
        """Get list of available providers with valid API keys"""
        if requested_providers:
            providers = requested_providers
        else:
            providers = list(LLMProvider)

        available = []
        for provider in providers:
            config = self._provider_configs.get(provider)
            if config and config["api_key"]:
                available.append(provider)
            else:
                logger.warning(
                    f"Provider {provider.value} not available (missing API key)"
                )

        return available

    async def _query_single_provider(
        self,
        provider: LLMProvider,
        prompt: str,
        system_prompt: str | None,
        timeout: float,
    ) -> tuple[LLMProvider, LLMResponse | Exception]:
        """Query a single provider with timeout handling"""
        try:
            config = self._provider_configs[provider]
            llm = LLMFactory.create(
                provider=provider,
                api_key=config["api_key"],
                model=config["model"],
            )

            start_time = time.time()
            response = await asyncio.wait_for(
                llm.generate(prompt=prompt, system_prompt=system_prompt),
                timeout=timeout,
            )
            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Provider {provider.value} responded in {elapsed_ms:.0f}ms "
                f"({response.tokens_used} tokens)"
            )

            return provider, response

        except TimeoutError:
            logger.error(f"Provider {provider.value} timed out after {timeout}s")
            return provider, TimeoutError(f"Request timed out after {timeout}s")
        except Exception as e:
            logger.error(f"Provider {provider.value} failed: {e}")
            return provider, e

    async def query_all(
        self,
        prompt: str,
        providers: list[LLMProvider] | None = None,
        system_prompt: str | None = None,
        timeout: float = 30.0,
    ) -> MultiLLMResponse:
        """
        Query multiple LLMs in parallel and return aggregated results

        Args:
            prompt: The prompt to send to all providers
            providers: List of providers to query (None = all available)
            system_prompt: Optional system prompt
            timeout: Timeout in seconds for each provider

        Returns:
            MultiLLMResponse with results from all providers
        """
        start_time = time.time()

        # Get available providers
        available_providers = self._get_available_providers(providers)
        if not available_providers:
            logger.error("No LLM providers available")
            return MultiLLMResponse(
                responses={},
                errors={},
                total_latency_ms=0.0,
                successful_count=0,
            )

        logger.info(
            f"Querying {len(available_providers)} providers: "
            f"{[p.value for p in available_providers]}"
        )

        # Query all providers in parallel
        tasks = [
            self._query_single_provider(provider, prompt, system_prompt, timeout)
            for provider in available_providers
        ]

        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Aggregate results
        responses = {}
        errors = {}

        for provider, result in results:
            if isinstance(result, LLMResponse):
                responses[provider] = result
            elif isinstance(result, Exception):
                errors[provider] = str(result)
            else:
                errors[provider] = "Unknown error"

        total_latency_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Multi-LLM query completed in {total_latency_ms:.0f}ms: "
            f"{len(responses)} successful, {len(errors)} failed"
        )

        return MultiLLMResponse(
            responses=responses,
            errors=errors,
            total_latency_ms=total_latency_ms,
            successful_count=len(responses),
        )

    async def query_with_fallback(
        self,
        prompt: str,
        preferred_provider: LLMProvider = LLMProvider.GEMINI,
        fallback_provider: LLMProvider = LLMProvider.OPENAI,
        system_prompt: str | None = None,
        timeout: float = 30.0,
    ) -> LLMResponse:
        """
        Query with automatic fallback on failure

        Args:
            prompt: The prompt to send
            preferred_provider: Primary provider to try first
            fallback_provider: Fallback provider if primary fails
            system_prompt: Optional system prompt
            timeout: Timeout in seconds per provider

        Returns:
            LLMResponse from successful provider

        Raises:
            RuntimeError: If both providers fail
        """
        logger.info(
            f"Attempting query with {preferred_provider.value} "
            f"(fallback: {fallback_provider.value})"
        )

        # Try preferred provider first
        provider, result = await self._query_single_provider(
            preferred_provider, prompt, system_prompt, timeout
        )

        if isinstance(result, LLMResponse):
            logger.info(
                f"Successfully used preferred provider: {preferred_provider.value}"
            )
            return result

        # Log failure and try fallback
        error_msg = str(result)
        logger.warning(
            f"Preferred provider {preferred_provider.value} failed: {error_msg}"
        )
        logger.info(f"Attempting fallback provider: {fallback_provider.value}")

        provider, result = await self._query_single_provider(
            fallback_provider, prompt, system_prompt, timeout
        )

        if isinstance(result, LLMResponse):
            logger.info(
                f"Successfully used fallback provider: {fallback_provider.value}"
            )
            return result

        # Both failed
        fallback_error = str(result)
        logger.error(
            f"Both providers failed. Preferred: {error_msg}, "
            f"Fallback: {fallback_error}"
        )
        raise RuntimeError(
            f"All providers failed. {preferred_provider.value}: {error_msg}, "
            f"{fallback_provider.value}: {fallback_error}"
        )
