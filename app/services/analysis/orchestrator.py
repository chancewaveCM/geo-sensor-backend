"""Unified Analysis Orchestrator.

Thin wrapper around PipelineOrchestratorService that provides
quick and advanced analysis modes with preset configurations.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import async_session_maker
from app.models.company_profile import CompanyProfile
from app.models.enums import LLMProvider, PipelineStatus
from app.models.pipeline_job import PipelineJob
from app.models.query_set import QuerySet
from app.services.llm.factory import LLMFactory
from app.services.pipeline.background_manager import BackgroundJobManager
from app.services.pipeline.category_generator import CategoryGeneratorService
from app.services.pipeline.orchestrator import PipelineOrchestratorService
from app.services.pipeline.query_executor import QueryExecutorService
from app.services.pipeline.query_expander import QueryExpanderService

logger = logging.getLogger(__name__)


# Mode presets
QUICK_MODE = {
    "category_count": 3,
    "queries_per_category": 10,
}

ADVANCED_MODE_DEFAULTS = {
    "category_count": 10,
    "queries_per_category": 10,
}


class UnifiedOrchestrator:
    """Orchestrates unified analysis jobs.

    Wraps PipelineOrchestratorService with mode-specific presets.
    Quick mode: 3 categories, 10 queries (fast overview).
    Advanced mode: User-configured (detailed analysis).
    """

    @staticmethod
    def get_mode_config(
        mode: str,
        category_count: int | None = None,
        queries_per_category: int | None = None,
    ) -> dict:
        """Get configuration for the given mode."""
        if mode == "quick":
            return QUICK_MODE.copy()
        # Advanced mode with user overrides
        config = ADVANCED_MODE_DEFAULTS.copy()
        if category_count is not None:
            config["category_count"] = category_count
        if queries_per_category is not None:
            config["queries_per_category"] = queries_per_category
        return config

    @staticmethod
    def _get_api_key(provider: LLMProvider) -> str:
        """Get API key for the given provider."""
        if provider == LLMProvider.GEMINI:
            return settings.GEMINI_API_KEY
        elif provider == LLMProvider.OPENAI:
            return settings.OPENAI_API_KEY
        raise ValueError(f"Unknown provider: {provider}")

    @classmethod
    def build_services(
        cls,
        llm_providers: list[str],
    ) -> tuple[PipelineOrchestratorService, AsyncSession]:
        """Build pipeline orchestrator with all required services.

        Returns (orchestrator, bg_db) — caller must close bg_db on error.
        """
        providers_dict = {
            LLMProvider(p): LLMFactory.create(
                LLMProvider(p), cls._get_api_key(LLMProvider(p))
            )
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

    @classmethod
    async def start_analysis(
        cls,
        db: AsyncSession,
        owner_id: int,
        company_profile_id: int,
        mode: str,
        llm_providers: list[str],
        category_count: int | None = None,
        queries_per_category: int | None = None,
    ) -> PipelineJob:
        """Start an analysis job with the given mode.

        Creates QuerySet + PipelineJob and launches background execution.
        Returns the created PipelineJob.
        """
        # Get mode config
        config = cls.get_mode_config(mode, category_count, queries_per_category)

        # Load company profile for naming
        result = await db.execute(
            select(CompanyProfile).where(CompanyProfile.id == company_profile_id)
        )
        profile = result.scalar_one_or_none()
        profile_name = profile.name if profile else f"Profile-{company_profile_id}"

        # Create QuerySet
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M")
        query_set = QuerySet(
            name=f"{profile_name} - {mode.title()} Analysis {timestamp}",
            description=f"{mode.title()} analysis for {profile_name}",
            category_count=config["category_count"],
            queries_per_category=config["queries_per_category"],
            company_profile_id=company_profile_id,
            owner_id=owner_id,
        )
        db.add(query_set)
        await db.commit()
        await db.refresh(query_set)

        # Create PipelineJob with mode
        job = PipelineJob(
            query_set_id=query_set.id,
            company_profile_id=company_profile_id,
            owner_id=owner_id,
            llm_providers=llm_providers,
            status=PipelineStatus.PENDING,
            mode=mode,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

        # Build services and start background execution
        orchestrator, bg_db = cls.build_services(llm_providers)
        try:
            await BackgroundJobManager.start_job(
                job.id,
                orchestrator.start_pipeline(
                    job_id=job.id,
                    company_profile_id=company_profile_id,
                    query_set_id=query_set.id,
                    is_rerun=False,
                ),
            )
        except Exception:
            await bg_db.close()
            raise

        return job
