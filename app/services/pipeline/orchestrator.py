"""Pipeline orchestration service."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_profile import CompanyProfile
from app.models.enums import ExpandedQueryStatus, LLMProvider, PersonaType, PipelineStatus
from app.models.expanded_query import ExpandedQuery
from app.models.pipeline_category import PipelineCategory
from app.models.pipeline_job import PipelineJob
from app.models.query_set import QuerySet
from app.services.pipeline.category_generator import CategoryGeneratorService
from app.services.pipeline.query_executor import QueryExecutorService
from app.services.pipeline.query_expander import QueryExpanderService

logger = logging.getLogger(__name__)


class PipelineOrchestratorService:
    """Orchestrate the full query pipeline execution."""

    def __init__(
        self,
        db: AsyncSession,
        category_generator: CategoryGeneratorService,
        query_expander: QueryExpanderService,
        query_executor: QueryExecutorService,
    ):
        self.db = db
        self.category_gen = category_generator
        self.query_expander = query_expander
        self.executor = query_executor

    async def start_pipeline(
        self,
        job: PipelineJob,
        company_profile: CompanyProfile,
        query_set: QuerySet,
        is_rerun: bool = False,
    ) -> None:
        """
        Execute the full pipeline:
        1. Generate categories (n per persona) - SKIP if rerun
        2. Expand to queries (m per category) - SKIP if rerun
        3. Execute queries against LLM providers
        4. Store normalized responses
        """
        try:
            job.started_at = datetime.utcnow()

            if is_rerun:
                # Rerun: Use existing categories and queries from QuerySet
                await self._update_status(job, PipelineStatus.EXECUTING_QUERIES)
                result = await self.db.execute(
                    select(ExpandedQuery)
                    .join(PipelineCategory)
                    .where(PipelineCategory.query_set_id == query_set.id)
                )
                queries = result.scalars().all()

                # Set total_queries for progress tracking in reruns
                provider_count = len(job.llm_providers)
                job.total_queries = len(queries) * provider_count
                await self.db.commit()
            else:
                # First run: Generate categories and queries
                await self._update_status(job, PipelineStatus.GENERATING_CATEGORIES)
                categories = await self._generate_categories(
                    job, company_profile, query_set
                )

                await self._update_status(job, PipelineStatus.EXPANDING_QUERIES)
                queries = await self._expand_queries(
                    job, company_profile, categories, query_set
                )

            # Execute queries (both first run and rerun)
            await self._update_status(job, PipelineStatus.EXECUTING_QUERIES)
            await self._execute_queries(job, queries)

            # Complete
            await self._complete_job(job)

        except Exception as e:
            logger.exception(f"Pipeline failed for job {job.id}")
            await self._fail_job(job, str(e))
            raise

    async def _update_status(self, job: PipelineJob, status: PipelineStatus) -> None:
        """Update job status and commit."""
        job.status = status
        await self.db.commit()
        logger.info(f"Job {job.id} status: {status.value}")

    async def _generate_categories(
        self,
        job: PipelineJob,
        profile: CompanyProfile,
        query_set: QuerySet,
    ) -> list[PipelineCategory]:
        """Generate categories for both personas with proper distribution."""
        categories = []

        # Fixed: Use ceiling division to handle odd counts
        consumer_count = (query_set.category_count + 1) // 2
        investor_count = query_set.category_count - consumer_count

        persona_counts = [
            (PersonaType.CONSUMER, consumer_count),
            (PersonaType.INVESTOR, investor_count),
        ]

        for persona, count in persona_counts:
            if count <= 0:
                continue

            generated = await self.category_gen.generate(profile, count, persona)

            for i, cat_data in enumerate(generated):
                category = PipelineCategory(
                    name=cat_data["name"],
                    description=cat_data.get("description"),
                    persona_type=persona,
                    order_index=len(categories) + 1,
                    company_profile_id=profile.id,
                    query_set_id=query_set.id,
                )
                self.db.add(category)
                categories.append(category)

        await self.db.commit()
        logger.info(f"Generated {len(categories)} categories")
        return categories

    async def _expand_queries(
        self,
        job: PipelineJob,
        profile: CompanyProfile,
        categories: list[PipelineCategory],
        query_set: QuerySet,
    ) -> list[ExpandedQuery]:
        """Expand all categories into queries."""
        queries = []

        for category in categories:
            query_texts = await self.query_expander.expand(
                profile, category, query_set.queries_per_category
            )
            for i, text in enumerate(query_texts):
                query = ExpandedQuery(
                    text=text,
                    order_index=i + 1,
                    category_id=category.id,
                )
                self.db.add(query)
                queries.append(query)

        # Calculate total expected responses
        provider_count = len(job.llm_providers)
        job.total_queries = len(queries) * provider_count

        await self.db.commit()
        logger.info(
            f"Expanded to {len(queries)} queries, "
            f"expecting {job.total_queries} total responses"
        )
        return queries

    async def _execute_queries(
        self,
        job: PipelineJob,
        queries: list[ExpandedQuery],
    ) -> None:
        """Execute all queries with progress tracking."""
        providers = [LLMProvider(p) for p in job.llm_providers]

        for query in queries:
            query.status = ExpandedQueryStatus.EXECUTING
            await self.db.commit()

            has_success = False
            for provider in providers:
                response = await self.executor.execute_single(query, provider, job.id)
                self.db.add(response)

                if response.error_message:
                    job.failed_queries += 1
                else:
                    job.completed_queries += 1
                    has_success = True

                await self.db.commit()

            query.status = (
                ExpandedQueryStatus.COMPLETED
                if has_success
                else ExpandedQueryStatus.FAILED
            )
            await self.db.commit()

    async def _complete_job(self, job: PipelineJob) -> None:
        """Mark job as completed."""
        job.status = PipelineStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        await self.db.commit()
        logger.info(
            f"Job {job.id} completed: "
            f"{job.completed_queries} successful, {job.failed_queries} failed"
        )

    async def _fail_job(self, job: PipelineJob, error_message: str) -> None:
        """Mark job as failed."""
        job.status = PipelineStatus.FAILED
        job.error_message = error_message
        job.completed_at = datetime.utcnow()
        await self.db.commit()
        logger.error(f"Job {job.id} failed: {error_message}")
