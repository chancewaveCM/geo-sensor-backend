"""Competitive benchmarking analysis service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import CampaignRun, RunResponse
from app.models.enums import RunStatus
from app.models.run_citation import RunCitation
from app.schemas.timeseries import (
    CompetitiveAlert,
    CompetitiveAlertsResponse,
    CompetitiveBrandEntry,
    CompetitiveOverviewResponse,
    CompetitiveTrendEntry,
    CompetitiveTrendsResponse,
)


class CompetitiveAnalyzer:
    """Service for competitive benchmarking queries."""

    @staticmethod
    async def get_competitive_overview(
        db: AsyncSession,
        campaign_id: int,
    ) -> CompetitiveOverviewResponse:
        """Get citation share matrix for all brands in the campaign."""
        # Total responses count
        total_resp_result = await db.execute(
            select(func.count(RunResponse.id))
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == RunStatus.COMPLETED.value,
            )
        )
        total_responses = total_resp_result.scalar() or 0

        # Total citations
        total_cit_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == RunStatus.COMPLETED.value,
            )
        )
        total_citations = total_cit_result.scalar() or 0

        # Group by brand
        brand_result = await db.execute(
            select(
                RunCitation.cited_brand,
                RunCitation.is_target_brand,
                func.count(RunCitation.id).label("count"),
            )
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == RunStatus.COMPLETED.value,
            )
            .group_by(RunCitation.cited_brand, RunCitation.is_target_brand)
            .order_by(func.count(RunCitation.id).desc())
        )

        brands: list[CompetitiveBrandEntry] = []
        rank = 1
        for row in brand_result:
            citation_share = row.count / total_citations if total_citations > 0 else 0.0
            brands.append(
                CompetitiveBrandEntry(
                    brand_name=row.cited_brand,
                    is_target=row.is_target_brand,
                    citation_share=round(citation_share, 4),
                    citation_count=row.count,
                    rank=rank,
                    change_from_previous=None,
                )
            )
            rank += 1

        return CompetitiveOverviewResponse(
            campaign_id=campaign_id,
            period="all_time",
            brands=brands,
            total_responses=total_responses,
        )

    @staticmethod
    async def get_competitive_trends(
        db: AsyncSession,
        campaign_id: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> CompetitiveTrendsResponse:
        """Get brand-vs-brand citation share over time (per run)."""
        # Get completed runs in date range
        run_query = (
            select(CampaignRun)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == RunStatus.COMPLETED.value,
            )
            .order_by(CampaignRun.run_number)
        )
        if date_from:
            run_query = run_query.where(CampaignRun.started_at >= date_from)
        if date_to:
            run_query = run_query.where(CampaignRun.started_at <= date_to)

        runs_result = await db.execute(run_query)
        runs = runs_result.scalars().all()

        entries: list[CompetitiveTrendEntry] = []

        for run in runs:
            run_date = run.started_at or run.created_at

            # Total citations for this run
            total_cit_result = await db.execute(
                select(func.count(RunCitation.id))
                .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
                .where(RunResponse.campaign_run_id == run.id)
            )
            total_cit = total_cit_result.scalar() or 0

            if total_cit == 0:
                continue

            # Per-brand counts for this run
            brand_result = await db.execute(
                select(
                    RunCitation.cited_brand,
                    func.count(RunCitation.id).label("count"),
                )
                .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
                .where(RunResponse.campaign_run_id == run.id)
                .group_by(RunCitation.cited_brand)
            )

            for row in brand_result:
                entries.append(
                    CompetitiveTrendEntry(
                        date=run_date,
                        brand_name=row.cited_brand,
                        citation_share=round(row.count / total_cit, 4),
                    )
                )

        # Determine actual date bounds from entries
        actual_from = min((e.date for e in entries), default=date_from or datetime.min)
        actual_to = max((e.date for e in entries), default=date_to or datetime.max)

        return CompetitiveTrendsResponse(
            campaign_id=campaign_id,
            date_from=actual_from,
            date_to=actual_to,
            entries=entries,
        )

    @staticmethod
    async def detect_significant_changes(
        db: AsyncSession,
        campaign_id: int,
        threshold: float = 5.0,
    ) -> CompetitiveAlertsResponse:
        """Detect alerts when brand share changes more than *threshold* percent.

        Compares the latest two completed runs.
        """
        # Get last two completed runs
        runs_result = await db.execute(
            select(CampaignRun)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == RunStatus.COMPLETED.value,
            )
            .order_by(CampaignRun.run_number.desc())
            .limit(2)
        )
        runs = runs_result.scalars().all()

        alerts: list[CompetitiveAlert] = []

        if len(runs) < 2:
            return CompetitiveAlertsResponse(campaign_id=campaign_id, alerts=alerts)

        latest_run, previous_run = runs[0], runs[1]

        async def _brand_shares(run_id: int) -> dict[str, float]:
            total_result = await db.execute(
                select(func.count(RunCitation.id))
                .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
                .where(RunResponse.campaign_run_id == run_id)
            )
            total = total_result.scalar() or 0
            if total == 0:
                return {}

            brand_result = await db.execute(
                select(
                    RunCitation.cited_brand,
                    func.count(RunCitation.id).label("count"),
                )
                .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
                .where(RunResponse.campaign_run_id == run_id)
                .group_by(RunCitation.cited_brand)
            )
            return {
                row.cited_brand: row.count / total for row in brand_result
            }

        latest_shares = await _brand_shares(latest_run.id)
        previous_shares = await _brand_shares(previous_run.id)

        all_brands = set(latest_shares) | set(previous_shares)

        for brand in all_brands:
            current_share = latest_shares.get(brand, 0.0) * 100
            prev_share = previous_shares.get(brand, 0.0) * 100
            change = current_share - prev_share

            if abs(change) >= threshold:
                direction = "up" if change > 0 else "down"
                severity = (
                    "critical"
                    if abs(change) >= threshold * 2
                    else "warning"
                    if abs(change) >= threshold
                    else "info"
                )
                alerts.append(
                    CompetitiveAlert(
                        brand_name=brand,
                        change_percent=round(change, 2),
                        direction=direction,
                        period="run_over_run",
                        severity=severity,
                    )
                )

        # Sort by absolute change descending
        alerts.sort(key=lambda a: abs(a.change_percent), reverse=True)

        return CompetitiveAlertsResponse(campaign_id=campaign_id, alerts=alerts)

    @staticmethod
    async def get_brand_rankings(
        db: AsyncSession,
        campaign_id: int,
    ) -> list[CompetitiveBrandEntry]:
        """Get current brand rankings ordered by citation share.

        Uses only the latest completed run for ranking.
        """
        # Find latest completed run
        latest_run_result = await db.execute(
            select(CampaignRun)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == RunStatus.COMPLETED.value,
            )
            .order_by(CampaignRun.run_number.desc())
            .limit(1)
        )
        latest_run = latest_run_result.scalar_one_or_none()

        if latest_run is None:
            return []

        # Total citations in latest run
        total_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .where(RunResponse.campaign_run_id == latest_run.id)
        )
        total = total_result.scalar() or 0

        if total == 0:
            return []

        # Per-brand breakdown
        brand_result = await db.execute(
            select(
                RunCitation.cited_brand,
                RunCitation.is_target_brand,
                func.count(RunCitation.id).label("count"),
            )
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .where(RunResponse.campaign_run_id == latest_run.id)
            .group_by(RunCitation.cited_brand, RunCitation.is_target_brand)
            .order_by(func.count(RunCitation.id).desc())
        )

        # Optionally compute change vs second-latest run
        prev_shares: dict[str, float] = {}
        second_run_result = await db.execute(
            select(CampaignRun)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == RunStatus.COMPLETED.value,
                CampaignRun.id != latest_run.id,
            )
            .order_by(CampaignRun.run_number.desc())
            .limit(1)
        )
        second_run = second_run_result.scalar_one_or_none()

        if second_run:
            prev_total_result = await db.execute(
                select(func.count(RunCitation.id))
                .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
                .where(RunResponse.campaign_run_id == second_run.id)
            )
            prev_total = prev_total_result.scalar() or 0

            if prev_total > 0:
                prev_brand_result = await db.execute(
                    select(
                        RunCitation.cited_brand,
                        func.count(RunCitation.id).label("count"),
                    )
                    .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
                    .where(RunResponse.campaign_run_id == second_run.id)
                    .group_by(RunCitation.cited_brand)
                )
                prev_shares = {
                    row.cited_brand: row.count / prev_total
                    for row in prev_brand_result
                }

        rankings: list[CompetitiveBrandEntry] = []
        rank = 1
        for row in brand_result:
            share = row.count / total
            prev = prev_shares.get(row.cited_brand)
            change = round((share - prev) * 100, 2) if prev is not None else None

            rankings.append(
                CompetitiveBrandEntry(
                    brand_name=row.cited_brand,
                    is_target=row.is_target_brand,
                    citation_share=round(share, 4),
                    citation_count=row.count,
                    rank=rank,
                    change_from_previous=change,
                )
            )
            rank += 1

        return rankings
