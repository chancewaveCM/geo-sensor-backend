"""LLM Query endpoints."""

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.llm.base import BaseLLMService, LLMProvider
from app.services.llm.factory import LLMFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])


# Request/Response Schemas
class LLMQueryRequest(BaseModel):
    """Request schema for LLM query."""
    prompt: str = Field(..., min_length=1, max_length=10000)
    providers: list[str] | None = None  # ["openai", "gemini"] or None for all
    system_prompt: str | None = None
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=1024, ge=1, le=4096)


class LLMSingleResponse(BaseModel):
    """Response from a single LLM provider."""
    provider: str
    model: str
    content: str
    tokens_used: int
    latency_ms: float


class LLMQueryResponse(BaseModel):
    """Response from LLM query endpoint."""
    responses: list[LLMSingleResponse]
    errors: dict[str, str]  # provider -> error
    total_latency_ms: float


class HealthCheckResponse(BaseModel):
    """Health check response for LLM providers."""
    openai: bool
    gemini: bool


class ProviderInfo(BaseModel):
    """Information about a provider."""
    name: str
    model: str
    available: bool


class ProvidersResponse(BaseModel):
    """List of available providers."""
    providers: list[ProviderInfo]


# Helper functions
def get_available_providers() -> dict[str, tuple[LLMProvider, str, str]]:
    """Get available LLM providers based on API keys."""
    available = {}

    if settings.OPENAI_API_KEY:
        available["openai"] = (
            LLMProvider.OPENAI,
            settings.OPENAI_API_KEY,
            settings.OPENAI_MODEL
        )

    if settings.GEMINI_API_KEY:
        available["gemini"] = (
            LLMProvider.GEMINI,
            settings.GEMINI_API_KEY,
            settings.GEMINI_MODEL
        )

    return available


async def query_single_provider(
    provider_name: str,
    llm_service: BaseLLMService,
    prompt: str,
    system_prompt: str | None,
    temperature: float,
    max_tokens: int,
) -> tuple[LLMSingleResponse | None, str | None]:
    """Query a single LLM provider."""
    try:
        start_time = time.time()
        response = await llm_service.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.time() - start_time) * 1000

        return LLMSingleResponse(
            provider=provider_name,
            model=response.model,
            content=response.content,
            tokens_used=response.tokens_used,
            latency_ms=latency_ms,
        ), None
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return None, "LLM generation failed"


# Endpoints
@router.post("/query", response_model=LLMQueryResponse)
async def query_llms(request: LLMQueryRequest) -> LLMQueryResponse:
    """
    Query one or multiple LLMs.

    If providers is None or empty, query all available providers.
    Returns results from all requested providers, with errors for failed ones.
    """
    start_time = time.time()

    # Get available providers
    available = get_available_providers()

    if not available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No LLM providers configured. Set OPENAI_API_KEY or GEMINI_API_KEY."
        )

    # Determine which providers to query
    if request.providers:
        # Validate requested providers
        invalid_providers = set(request.providers) - set(available.keys())
        if invalid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid providers: {', '.join(invalid_providers)}"
            )
        target_providers = {k: available[k] for k in request.providers}
    else:
        # Query all available providers
        target_providers = available

    # Create LLM service instances
    llm_services = {}
    for provider_name, (provider_enum, api_key, model) in target_providers.items():
        try:
            llm_services[provider_name] = LLMFactory.create(
                provider=provider_enum,
                api_key=api_key,
                model=model,
                cache=True,
            )
        except Exception as e:
            # If we can't create the service, skip it
            logger.error(f"Failed to create LLM service for {provider_name}: {e}")
            continue

    if not llm_services:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to initialize any LLM providers"
        )

    # Query all providers in parallel
    tasks = [
        query_single_provider(
            provider_name=provider_name,
            llm_service=service,
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        for provider_name, service in llm_services.items()
    ]

    results = await asyncio.gather(*tasks)

    # Collect responses and errors
    responses = []
    errors = {}

    for (provider_name, _), (response, error) in zip(llm_services.items(), results):
        if response:
            responses.append(response)
        elif error:
            errors[provider_name] = error

    total_latency_ms = (time.time() - start_time) * 1000

    return LLMQueryResponse(
        responses=responses,
        errors=errors,
        total_latency_ms=total_latency_ms,
    )


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Check health of all LLM providers."""
    available = get_available_providers()

    # Check OpenAI
    openai_healthy = False
    if "openai" in available:
        try:
            provider_enum, api_key, model = available["openai"]
            service = LLMFactory.create(provider_enum, api_key, model, cache=True)
            openai_healthy = await service.health_check()
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            openai_healthy = False

    # Check Gemini
    gemini_healthy = False
    if "gemini" in available:
        try:
            provider_enum, api_key, model = available["gemini"]
            service = LLMFactory.create(provider_enum, api_key, model, cache=True)
            gemini_healthy = await service.health_check()
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            gemini_healthy = False

    return HealthCheckResponse(
        openai=openai_healthy,
        gemini=gemini_healthy,
    )


@router.get("/providers", response_model=ProvidersResponse)
async def list_providers() -> ProvidersResponse:
    """List available LLM providers and their models."""
    available = get_available_providers()

    providers = []

    # Check each provider
    for provider_name, (provider_enum, api_key, model) in available.items():
        try:
            service = LLMFactory.create(provider_enum, api_key, model, cache=True)
            is_available = await service.health_check()
        except Exception as e:
            logger.warning(f"Provider {provider_name} health check failed: {e}")
            is_available = False

        providers.append(ProviderInfo(
            name=provider_name,
            model=model,
            available=is_available,
        ))

    return ProvidersResponse(providers=providers)
