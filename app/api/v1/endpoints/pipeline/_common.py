# app/api/v1/endpoints/pipeline/_common.py

from typing import Literal

from fastapi import HTTPException, Response, status

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.enums import LLMProvider
from app.services.llm.factory import LLMFactory
from app.services.pipeline.background_manager import BackgroundJobManager
from app.services.pipeline.category_generator import CategoryGeneratorService
from app.services.pipeline.orchestrator import PipelineOrchestratorService
from app.services.pipeline.query_executor import QueryExecutorService
from app.services.pipeline.query_expander import QueryExpanderService

SUNSET_DATE = "Mon, 01 Jun 2026 00:00:00 GMT"
SUNSET_LINK = "</api/v1/unified-analysis/start>; rel=\"successor-version\""


def _add_sunset_headers(response: Response) -> None:
    """Add Sunset headers to indicate API deprecation."""
    response.headers["Sunset"] = SUNSET_DATE
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = SUNSET_LINK


def _calculate_health_grade(
    success_rate_30d: float,
    data_freshness_hours: float | None,
    consecutive_failures: int,
    total_query_sets: int,
) -> Literal["green", "yellow", "red"]:
    """Calculate health grade based on KPI rules."""
    if (
        success_rate_30d < 60
        or (data_freshness_hours is not None and data_freshness_hours >= 72)
        or consecutive_failures >= 3
        or total_query_sets == 0
    ):
        return "red"
    if (
        success_rate_30d < 90
        or (data_freshness_hours is not None and 24 <= data_freshness_hours < 72)
    ):
        return "yellow"
    return "green"


def _validate_llm_providers(providers: list[str]) -> None:
    """Validate that all provider strings are valid LLMProvider values."""
    valid_providers = {p.value for p in LLMProvider}
    for provider in providers:
        if provider not in valid_providers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider: {provider}. Valid: {valid_providers}",
            )


def _build_pipeline_services(
    llm_providers: list[str],
) -> tuple[PipelineOrchestratorService, BackgroundJobManager]:
    """Build pipeline orchestrator with all required services.

    Returns (orchestrator, bg_db) - caller must close bg_db on error.
    """
    def _get_api_key(provider: LLMProvider) -> str:
        if provider == LLMProvider.GEMINI:
            return settings.GEMINI_API_KEY
        elif provider == LLMProvider.OPENAI:
            return settings.OPENAI_API_KEY
        raise ValueError(f"Unknown provider: {provider}")

    providers_dict = {
        LLMProvider(p): LLMFactory.create(LLMProvider(p), _get_api_key(LLMProvider(p)))
        for p in llm_providers
    }

    category_generators = {
        provider: CategoryGeneratorService(llm)
        for provider, llm in providers_dict.items()
    }
    query_expanders = {
        provider: QueryExpanderService(llm)
        for provider, llm in providers_dict.items()
    }
    query_executor = QueryExecutorService(providers_dict)
    bg_db = async_session_maker()
    orchestrator = PipelineOrchestratorService(
        bg_db, category_generators, query_expanders, query_executor
    )
    return orchestrator, bg_db
