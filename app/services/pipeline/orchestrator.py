"""Pipeline orchestration service."""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
        category_generators: dict[LLMProvider, CategoryGeneratorService],
        query_expanders: dict[LLMProvider, QueryExpanderService],
        query_executor: QueryExecutorService,
    ):
        self.db = db
        self.category_generators = category_generators
        self.query_expanders = query_expanders
        self.executor = query_executor

    async def start_pipeline(
        self,
        job_id: int,
        company_profile_id: int,
        query_set_id: int,
        is_rerun: bool = False,
    ) -> None:
        """
        Execute the full pipeline:
        1. Generate categories (n per persona) - SKIP if rerun
        2. Expand to queries (m per category) - SKIP if rerun
        3. Execute queries against LLM providers
        4. Store normalized responses
        """
        job: PipelineJob | None = None

        try:
            job = await self.db.get(PipelineJob, job_id)
            company_profile = await self.db.get(CompanyProfile, company_profile_id)
            query_set = await self.db.get(QuerySet, query_set_id)

            if not job or not company_profile or not query_set:
                raise ValueError(
                    f"Pipeline resources not found: "
                    f"job={job_id}, profile={company_profile_id}, query_set={query_set_id}"
                )

            job.started_at = datetime.utcnow()

            if is_rerun:
                # Rerun: Use existing categories and queries from QuerySet
                await self._update_status(job, PipelineStatus.EXECUTING_QUERIES)
                selected_providers = [LLMProvider(p) for p in job.llm_providers]
                result = await self.db.execute(
                    select(ExpandedQuery)
                    .join(PipelineCategory)
                    .where(PipelineCategory.query_set_id == query_set.id)
                    .where(PipelineCategory.llm_provider.in_(selected_providers))
                    .options(selectinload(ExpandedQuery.category))
                )
                queries = result.scalars().all()
                query_entries = [(query, query.category.llm_provider) for query in queries]

                # Set total_queries for progress tracking in reruns
                job.total_queries = len(query_entries)
                await self.db.commit()
            else:
                # First run: Generate categories and queries
                await self._update_status(job, PipelineStatus.GENERATING_CATEGORIES)
                categories = await self._generate_categories(
                    job, company_profile, query_set
                )

                await self._update_status(job, PipelineStatus.EXPANDING_QUERIES)
                query_entries = await self._expand_queries(
                    job, company_profile, categories, query_set
                )

            # Execute queries (both first run and rerun)
            await self._update_status(job, PipelineStatus.EXECUTING_QUERIES)
            await self._execute_queries(job, query_entries)

            # Complete
            await self._complete_job(job)

        except Exception as e:
            logger.exception(f"Pipeline failed for job {job_id}")
            if job is not None:
                await self._fail_job(job, str(e))
            raise
        finally:
            await self.db.close()

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
        selected_providers = [LLMProvider(p) for p in job.llm_providers]

        for provider in selected_providers:
            generator = self.category_generators.get(provider)
            if generator is None:
                raise ValueError(f"Category generator not configured for provider={provider.value}")

            # Use ceiling division to handle odd counts.
            consumer_count = (query_set.category_count + 1) // 2
            investor_count = query_set.category_count - consumer_count

            persona_counts = [
                (PersonaType.CONSUMER, consumer_count),
                (PersonaType.INVESTOR, investor_count),
            ]

            for persona, count in persona_counts:
                if count <= 0:
                    continue

                generated = await generator.generate(profile, count, persona)

                for cat_data in generated:
                    category = PipelineCategory(
                        name=cat_data["name"],
                        description=cat_data.get("description"),
                        persona_type=persona,
                        llm_provider=provider,
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
    ) -> list[tuple[ExpandedQuery, LLMProvider]]:
        """Expand all categories into queries."""
        query_entries: list[tuple[ExpandedQuery, LLMProvider]] = []

        for category in categories:
            expander = self.query_expanders.get(category.llm_provider)
            if expander is None:
                raise ValueError(
                    f"Query expander not configured for provider={category.llm_provider.value}"
                )

            query_texts = await expander.expand(
                profile, category, query_set.queries_per_category
            )
            for i, text in enumerate(query_texts):
                query = ExpandedQuery(
                    text=text,
                    order_index=i + 1,
                    category_id=category.id,
                )
                self.db.add(query)
                query_entries.append((query, category.llm_provider))

        # Provider-specific pipeline executes each expanded query with its own provider once.
        job.total_queries = len(query_entries)

        await self.db.commit()
        logger.info(
            f"Expanded to {len(query_entries)} queries, "
            f"expecting {job.total_queries} total responses"
        )
        return query_entries

    async def _execute_queries(
        self,
        job: PipelineJob,
        query_entries: list[tuple[ExpandedQuery, LLMProvider]],
    ) -> None:
        """Execute all queries with progress tracking."""
        for query, provider in query_entries:
            query.status = ExpandedQueryStatus.EXECUTING
            await self.db.commit()

            response = await self.executor.execute_single(query, provider, job.id)
            self.db.add(response)

            if response.error_message:
                job.failed_queries += 1
                query.status = ExpandedQueryStatus.FAILED
            else:
                job.completed_queries += 1
                query.status = ExpandedQueryStatus.COMPLETED

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
