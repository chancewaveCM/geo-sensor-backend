"""Campaign run executor - executes queries against LLMs and stores results."""

import hashlib
import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.campaign import (
    Campaign,
    CampaignCompany,
    CampaignRun,
    QueryDefinition,
    QueryVersion,
    RunResponse,
)
from app.models.company_profile import CompanyProfile
from app.models.enums import RunStatus
from app.services.campaign.citation_extraction import CitationExtractionService
from app.services.llm import LLMProvider, MultiLLMService

logger = logging.getLogger(__name__)


class CampaignRunExecutor:
    """Executes a campaign run: queries LLMs, stores responses, extracts citations."""

    def __init__(self):
        self.multi_llm = MultiLLMService()
        self.citation_service = CitationExtractionService()

    async def execute_run(self, campaign_run_id: int) -> None:
        """Execute a full campaign run end-to-end."""
        async with async_session_maker() as db:
            try:
                # Load campaign run
                run_result = await db.execute(
                    select(CampaignRun).where(CampaignRun.id == campaign_run_id)
                )
                campaign_run = run_result.scalar_one_or_none()
                if campaign_run is None:
                    logger.error("CampaignRun %d not found", campaign_run_id)
                    return

                if campaign_run.status != RunStatus.PENDING.value:
                    logger.warning(
                        "CampaignRun %d is not pending (status=%s), skipping",
                        campaign_run_id,
                        campaign_run.status,
                    )
                    return

                # Mark as executing
                campaign_run.status = RunStatus.EXECUTING.value
                campaign_run.started_at = datetime.now(tz=UTC)
                await db.commit()

                # Load campaign for context
                campaign_result = await db.execute(
                    select(Campaign).where(Campaign.id == campaign_run.campaign_id)
                )
                campaign = campaign_result.scalar_one()

                # Get brand names for citation extraction
                brand_names = await self._get_brand_names(db, campaign.id)

                # Parse LLM providers from run config
                providers = self._parse_providers(campaign_run.llm_providers)

                # Get active query versions
                query_versions = await self._get_active_query_versions(
                    db, campaign.id
                )

                if not query_versions:
                    logger.warning(
                        "No active queries for campaign %d", campaign.id
                    )
                    campaign_run.status = RunStatus.COMPLETED.value
                    campaign_run.completed_at = datetime.now(tz=UTC)
                    campaign_run.total_queries = 0
                    await db.commit()
                    return

                campaign_run.total_queries = len(query_versions) * len(providers)
                await db.commit()

                completed = 0
                failed = 0

                # Execute each query against all providers
                for qv in query_versions:
                    try:
                        multi_response = await self.multi_llm.query_all(
                            prompt=qv.text,
                            providers=[
                                LLMProvider(p) for p in providers
                                if p in [lp.value for lp in LLMProvider]
                            ],
                            timeout=60.0,
                        )

                        # Store successful responses
                        for provider, llm_response in multi_response.responses.items():
                            try:
                                run_response = await self._store_response(
                                    db,
                                    campaign_run.id,
                                    qv.id,
                                    provider.value,
                                    llm_response.model,
                                    llm_response.content,
                                    llm_response.latency_ms,
                                )

                                # Extract and store citations
                                await self.citation_service.extract_citations(
                                    response=run_response,
                                    target_brands=brand_names,
                                    db=db,
                                )

                                completed += 1
                            except Exception:
                                logger.exception(
                                    "Failed to store response for query %d, provider %s",
                                    qv.id,
                                    provider.value,
                                )
                                failed += 1

                        # Count errors as failed
                        failed += len(multi_response.errors)

                        # Update progress
                        campaign_run.completed_queries = completed
                        campaign_run.failed_queries = failed
                        await db.commit()

                    except Exception:
                        logger.exception(
                            "Failed to execute query version %d", qv.id
                        )
                        failed += len(providers)
                        campaign_run.failed_queries = failed
                        await db.commit()

                # Mark run as completed
                campaign_run.status = RunStatus.COMPLETED.value
                campaign_run.completed_at = datetime.now(tz=UTC)
                campaign_run.completed_queries = completed
                campaign_run.failed_queries = failed
                await db.commit()

                logger.info(
                    "CampaignRun %d completed: %d OK, %d failed",
                    campaign_run_id,
                    completed,
                    failed,
                )

            except Exception as e:
                logger.exception("CampaignRun %d failed", campaign_run_id)
                try:
                    campaign_run.status = RunStatus.FAILED.value
                    campaign_run.completed_at = datetime.now(tz=UTC)
                    campaign_run.error_message = str(e)[:500]
                    await db.commit()
                except Exception:
                    logger.exception("Failed to update run status to FAILED")

    async def _get_brand_names(
        self, db: AsyncSession, campaign_id: int
    ) -> list[str]:
        """Get brand names for citation extraction."""
        result = await db.execute(
            select(CompanyProfile.name)
            .join(
                CampaignCompany,
                CampaignCompany.company_profile_id == CompanyProfile.id,
            )
            .where(CampaignCompany.campaign_id == campaign_id)
        )
        return [name for (name,) in result.all()]

    def _parse_providers(self, llm_providers_json: str | None) -> list[str]:
        """Parse LLM providers from JSON string."""
        if not llm_providers_json:
            return ["openai", "gemini"]
        try:
            providers = json.loads(llm_providers_json)
            if isinstance(providers, list):
                return providers
        except (json.JSONDecodeError, TypeError):
            pass
        return ["openai", "gemini"]

    async def _get_active_query_versions(
        self, db: AsyncSession, campaign_id: int
    ) -> list[QueryVersion]:
        """Get current versions of all active query definitions."""
        result = await db.execute(
            select(QueryVersion)
            .join(
                QueryDefinition,
                QueryVersion.query_definition_id == QueryDefinition.id,
            )
            .where(
                QueryDefinition.campaign_id == campaign_id,
                QueryDefinition.is_active.is_(True),
                QueryDefinition.is_retired.is_(False),
                QueryVersion.is_current.is_(True),
            )
        )
        return list(result.scalars().all())

    async def _store_response(
        self,
        db: AsyncSession,
        campaign_run_id: int,
        query_version_id: int,
        llm_provider: str,
        llm_model: str,
        content: str,
        latency_ms: float,
    ) -> RunResponse:
        """Store a single LLM response."""
        response_hash = hashlib.sha256(content.encode()).hexdigest()
        word_count = len(content.split())

        run_response = RunResponse(
            campaign_run_id=campaign_run_id,
            query_version_id=query_version_id,
            llm_provider=llm_provider,
            llm_model=llm_model,
            content=content,
            response_hash=response_hash,
            word_count=word_count,
            citation_count=0,  # Updated by extract_citations
            latency_ms=latency_ms,
        )
        db.add(run_response)
        await db.flush()
        return run_response
