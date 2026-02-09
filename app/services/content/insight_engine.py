"""Rule-based insight generation engine."""
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import CampaignRun, RunResponse
from app.models.insight import Insight
from app.models.run_citation import RunCitation

logger = logging.getLogger(__name__)


class InsightEngine:
    """Generates insights from campaign run data using 3 rules."""

    async def generate_insights(
        self, db: AsyncSession, campaign_id: int, workspace_id: int
    ) -> list[Insight]:
        """Generate all applicable insights for a campaign."""
        insights = []

        # Get completed runs ordered by date
        runs_result = await db.execute(
            select(CampaignRun)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == "completed",
            )
            .order_by(CampaignRun.started_at.asc())
        )
        runs = list(runs_result.scalars().all())

        if not runs:
            return insights

        # Rule 1: Provider Gap
        provider_gap = await self._check_provider_gap(db, campaign_id, workspace_id, runs[-1])
        if provider_gap:
            insights.append(provider_gap)

        # Rule 2: Citation Drop (compare last 2 runs)
        if len(runs) >= 2:
            drop = await self._check_citation_drop(
                db, campaign_id, workspace_id, runs[-2], runs[-1]
            )
            if drop:
                insights.append(drop)

        # Rule 3: Positive Trend (3 consecutive runs increasing)
        if len(runs) >= 3:
            trend = await self._check_positive_trend(db, campaign_id, workspace_id, runs[-3:])
            if trend:
                insights.append(trend)

        # Save insights to DB
        for insight in insights:
            db.add(insight)
        if insights:
            await db.commit()

        return insights

    async def _get_citation_share_for_run(
        self, db: AsyncSession, run_id: int
    ) -> tuple[float, dict[str, float]]:
        """Get overall citation share and per-provider shares for a run."""
        # Get all responses for this run
        resp_result = await db.execute(
            select(RunResponse).where(RunResponse.campaign_run_id == run_id)
        )
        responses = list(resp_result.scalars().all())

        if not responses:
            return 0.0, {}

        # Get all citations for these responses
        response_ids = [r.id for r in responses]
        cit_result = await db.execute(
            select(RunCitation).where(RunCitation.run_response_id.in_(response_ids))
        )
        citations = list(cit_result.scalars().all())

        if not citations:
            return 0.0, {}

        total = len(citations)
        target_count = sum(1 for c in citations if c.is_target_brand)
        overall_share = target_count / total if total > 0 else 0.0

        # Per-provider
        provider_shares = {}
        for resp in responses:
            resp_citations = [c for c in citations if c.run_response_id == resp.id]
            if resp_citations:
                provider = resp.llm_provider
                t_count = sum(1 for c in resp_citations if c.is_target_brand)
                share = t_count / len(resp_citations) if resp_citations else 0.0
                if provider not in provider_shares:
                    provider_shares[provider] = []
                provider_shares[provider].append(share)

        # Average per provider
        avg_provider_shares = {
            p: sum(shares) / len(shares) for p, shares in provider_shares.items()
        }

        return overall_share, avg_provider_shares

    async def _check_provider_gap(
        self, db: AsyncSession, campaign_id: int, workspace_id: int, latest_run: CampaignRun
    ) -> Insight | None:
        """Rule 1: Provider Gap - max share - min share > 10%p."""
        _, provider_shares = await self._get_citation_share_for_run(db, latest_run.id)

        if len(provider_shares) < 2:
            return None

        max_provider = max(provider_shares, key=provider_shares.get)
        min_provider = min(provider_shares, key=provider_shares.get)
        gap = provider_shares[max_provider] - provider_shares[min_provider]

        if gap > 0.10:  # 10%p threshold
            return Insight(
                workspace_id=workspace_id,
                campaign_id=campaign_id,
                insight_type="provider_gap",
                severity="warning",
                title=f"Provider gap detected: {max_provider} vs {min_provider}",
                description=(
                    f"Target brand citation rate is "
                    f"{provider_shares[max_provider]:.1%} on {max_provider} "
                    f"but only {provider_shares[min_provider]:.1%} on {min_provider} "
                    f"(gap: {gap:.1%}). Consider optimizing content for {min_provider}."
                ),
                data_json=json.dumps({
                    "max_provider": max_provider,
                    "max_share": round(provider_shares[max_provider], 4),
                    "min_provider": min_provider,
                    "min_share": round(provider_shares[min_provider], 4),
                    "gap": round(gap, 4),
                }),
            )
        return None

    async def _check_citation_drop(
        self, db: AsyncSession, campaign_id: int, workspace_id: int,
        prev_run: CampaignRun, curr_run: CampaignRun
    ) -> Insight | None:
        """Rule 2: Citation Drop - WoW change < -5%p."""
        prev_share, _ = await self._get_citation_share_for_run(db, prev_run.id)
        curr_share, _ = await self._get_citation_share_for_run(db, curr_run.id)

        change = curr_share - prev_share

        if change < -0.05:  # -5%p threshold
            return Insight(
                workspace_id=workspace_id,
                campaign_id=campaign_id,
                insight_type="citation_drop",
                severity="critical",
                title=f"Citation share dropped {abs(change):.1%}",
                description=(
                    f"Target brand citation rate dropped from {prev_share:.1%} to {curr_share:.1%} "
                    f"(change: {change:.1%}). Investigate recent content or competitor changes."
                ),
                data_json=json.dumps({
                    "previous_share": round(prev_share, 4),
                    "current_share": round(curr_share, 4),
                    "change": round(change, 4),
                    "prev_run_id": prev_run.id,
                    "curr_run_id": curr_run.id,
                }),
            )
        return None

    async def _check_positive_trend(
        self, db: AsyncSession, campaign_id: int, workspace_id: int,
        last_3_runs: list[CampaignRun]
    ) -> Insight | None:
        """Rule 3: Positive Trend - 3 consecutive increases."""
        shares = []
        for run in last_3_runs:
            share, _ = await self._get_citation_share_for_run(db, run.id)
            shares.append(share)

        if len(shares) == 3 and shares[0] < shares[1] < shares[2]:
            return Insight(
                workspace_id=workspace_id,
                campaign_id=campaign_id,
                insight_type="positive_trend",
                severity="info",
                title="Citation share rising for 3 consecutive runs",
                description=(
                    f"Target brand citation rate has been increasing: "
                    f"{shares[0]:.1%} → {shares[1]:.1%} → {shares[2]:.1%}. "
                    f"Current strategy appears effective."
                ),
                data_json=json.dumps({
                    "shares": [round(s, 4) for s in shares],
                    "run_ids": [r.id for r in last_3_runs],
                }),
            )
        return None
