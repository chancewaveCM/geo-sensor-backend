"""Query execution service with rate limiting."""

import asyncio
import logging
import time

from app.core.config import settings
from app.models.enums import LLMProvider
from app.models.expanded_query import ExpandedQuery
from app.models.raw_llm_response import RawLLMResponse
from app.services.llm.base import BaseLLMService
from app.services.llm.prompts import QUERY_EXECUTION_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class QueryExecutorService:
    """Execute queries against LLM providers with rate limiting."""

    def __init__(self, providers: dict[LLMProvider, BaseLLMService]):
        self.providers = providers
        # Semaphores for rate limiting per provider
        self._semaphores = {
            provider: asyncio.Semaphore(settings.PIPELINE_MAX_CONCURRENT_LLM_CALLS)
            for provider in providers.keys()
        }

    async def execute_single(
        self,
        query: ExpandedQuery,
        provider: LLMProvider,
        pipeline_job_id: int,
    ) -> RawLLMResponse:
        """
        Execute a single query against a provider with rate limiting.

        Returns:
            RawLLMResponse object (not yet persisted)
        """
        llm = self.providers.get(provider)
        if not llm:
            return self._create_error_response(
                query,
                provider,
                pipeline_job_id,
                Exception(f"Provider {provider} not configured"),
            )

        async with self._semaphores[provider]:
            # Add small delay between calls
            await asyncio.sleep(settings.PIPELINE_LLM_CALL_DELAY_MS / 1000)

            start_time = time.perf_counter()
            try:
                response = await asyncio.wait_for(
                    llm.generate(query.text, system_prompt=QUERY_EXECUTION_SYSTEM_PROMPT),
                    timeout=settings.PIPELINE_LLM_TIMEOUT_SECONDS,
                )
                latency_ms = (time.perf_counter() - start_time) * 1000
                return self._normalize_response(
                    query, provider, pipeline_job_id, response, latency_ms
                )
            except TimeoutError:
                return self._create_error_response(
                    query,
                    provider,
                    pipeline_job_id,
                    Exception(
                        f"Timeout after {settings.PIPELINE_LLM_TIMEOUT_SECONDS}s"
                    ),
                )
            except Exception as e:
                logger.error(f"Query execution failed: {e}")
                return self._create_error_response(query, provider, pipeline_job_id, e)

    def _normalize_response(
        self,
        query: ExpandedQuery,
        provider: LLMProvider,
        pipeline_job_id: int,
        response,
        latency_ms: float,
    ) -> RawLLMResponse:
        """Normalize LLM response to standard format."""
        return RawLLMResponse(
            content=response.content,
            llm_provider=provider,
            llm_model=response.model,
            tokens_used=response.tokens_used,
            latency_ms=latency_ms,
            raw_response_json=response.raw_response,
            query_id=query.id,
            pipeline_job_id=pipeline_job_id,
        )

    def _create_error_response(
        self,
        query: ExpandedQuery,
        provider: LLMProvider,
        pipeline_job_id: int,
        error: Exception,
    ) -> RawLLMResponse:
        """Create error response for failed execution."""
        return RawLLMResponse(
            content="",
            llm_provider=provider,
            llm_model="unknown",
            error_message=str(error),
            query_id=query.id,
            pipeline_job_id=pipeline_job_id,
        )
