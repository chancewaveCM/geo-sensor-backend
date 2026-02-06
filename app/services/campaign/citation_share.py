"""Citation Share calculation service."""

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import CampaignRun, RunResponse
from app.models.run_citation import RunCitation

logger = logging.getLogger(__name__)


class CitationShareService:
    """Calculate Citation Share metrics at various aggregation levels."""

    def compute_per_query(
        self, brand_name: str, citations: list[RunCitation]
    ) -> float:
        """Citation Share for a single RunResponse."""
        if not citations:
            return 0.0
        brand_count = sum(
            1 for c in citations if c.cited_brand.lower() == brand_name.lower()
        )
        return brand_count / len(citations)

    def compute_per_run(
        self, brand_name: str, all_citations: list[RunCitation]
    ) -> float:
        """Citation Share across all responses in a CampaignRun."""
        if not all_citations:
            return 0.0
        brand_count = sum(
            1 for c in all_citations if c.cited_brand.lower() == brand_name.lower()
        )
        return brand_count / len(all_citations)

    def compute_by_provider(
        self,
        brand_name: str,
        responses: list[RunResponse],
        all_citations: list[RunCitation],
    ) -> dict[str, float]:
        """Citation Share broken down by LLM provider."""
        result = {}
        providers = {r.llm_provider for r in responses}

        for provider in providers:
            provider_response_ids = {
                r.id for r in responses if r.llm_provider == provider
            }
            provider_citations = [
                c for c in all_citations if c.run_response_id in provider_response_ids
            ]
            result[provider] = self.compute_per_run(brand_name, provider_citations)

        return result

    async def compute_timeseries(
        self,
        db: AsyncSession,
        campaign_id: int,
        brand_name: str,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        """Compute Citation Share timeseries for a campaign."""
        # Get all completed runs for this campaign
        runs_query = (
            select(CampaignRun)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == "completed",
            )
            .order_by(CampaignRun.started_at)
        )
        result = await db.execute(runs_query)
        runs = result.scalars().all()

        timeseries = []
        for run in runs:
            # Get responses for this run
            resp_query = select(RunResponse).where(
                RunResponse.campaign_run_id == run.id
            )
            if provider:
                resp_query = resp_query.where(RunResponse.llm_provider == provider)

            resp_result = await db.execute(resp_query)
            responses = resp_result.scalars().all()
            response_ids = [r.id for r in responses]

            if not response_ids:
                continue

            # Get citations for these responses
            cit_query = select(RunCitation).where(
                RunCitation.run_response_id.in_(response_ids)
            )
            cit_result = await db.execute(cit_query)
            citations = cit_result.scalars().all()

            overall_share = self.compute_per_run(brand_name, citations)
            by_provider = self.compute_by_provider(brand_name, responses, citations)

            timeseries.append({
                "run_id": run.id,
                "timestamp": run.started_at or run.created_at,
                "citation_share_overall": overall_share,
                "citation_share_by_provider": by_provider,
                "total_citations": len(citations),
                "brand_citations": sum(
                    1 for c in citations if c.cited_brand.lower() == brand_name.lower()
                ),
            })

        return timeseries

    async def compute_campaign_summary(
        self,
        db: AsyncSession,
        campaign_id: int,
    ) -> dict[str, Any]:
        """Compute summary statistics for a campaign."""
        # Total runs
        run_count = await db.execute(
            select(func.count(CampaignRun.id)).where(
                CampaignRun.campaign_id == campaign_id
            )
        )
        total_runs = run_count.scalar() or 0

        # Total responses
        resp_count = await db.execute(
            select(func.count(RunResponse.id))
            .join(CampaignRun)
            .where(CampaignRun.campaign_id == campaign_id)
        )
        total_responses = resp_count.scalar() or 0

        # Total citations
        cit_count = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse)
            .join(CampaignRun)
            .where(CampaignRun.campaign_id == campaign_id)
        )
        total_citations = cit_count.scalar() or 0

        # Latest run
        latest_run_result = await db.execute(
            select(CampaignRun)
            .where(CampaignRun.campaign_id == campaign_id)
            .order_by(CampaignRun.created_at.desc())
            .limit(1)
        )
        latest_run = latest_run_result.scalar_one_or_none()

        return {
            "campaign_id": campaign_id,
            "total_runs": total_runs,
            "total_responses": total_responses,
            "total_citations": total_citations,
            "latest_run": latest_run,
        }
