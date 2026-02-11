"""Campaign analytics service - extracted from campaigns endpoint."""

from sqlalchemy import Float, Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import CampaignRun, QueryVersion, RunResponse
from app.models.enums import RunStatus
from app.models.run_citation import RunCitation
from app.schemas.campaign import (
    BrandRankingItem,
    BrandRankingResponse,
    BrandSafetyIncident,
    BrandSafetyMetrics,
    CampaignRunResponse,
    CampaignSummaryResponse,
    CitationShareResponse,
    GEOScoreSummaryResponse,
    ProviderComparisonResponse,
    ProviderMetrics,
    TimeseriesDataPoint,
    TimeseriesResponse,
)


class CampaignAnalyticsService:
    """Service for campaign analytics queries."""

    @staticmethod
    async def get_citation_share(
        db: AsyncSession,
        campaign_id: int,
    ) -> CitationShareResponse:
        """Get citation share breakdown for a campaign."""
        # Total citations count
        total_cit_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(CampaignRun.campaign_id == campaign_id)
        )
        total_citations = total_cit_result.scalar() or 0

        # Target brand citations count
        target_cit_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.is_target_brand.is_(True),
            )
        )
        target_brand_citations = target_cit_result.scalar() or 0

        # Overall citation share
        overall_citation_share = (
            target_brand_citations / total_citations if total_citations > 0 else 0.0
        )

        # By provider
        by_provider_result = await db.execute(
            select(
                RunResponse.llm_provider,
                func.count(RunCitation.id).label("total"),
                func.sum(func.cast(RunCitation.is_target_brand, Integer)).label("target"),
            )
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(CampaignRun.campaign_id == campaign_id)
            .group_by(RunResponse.llm_provider)
        )
        by_provider = {}
        for row in by_provider_result:
            provider_share = row.target / row.total if row.total > 0 else 0.0
            by_provider[row.llm_provider] = provider_share

        # By brand
        by_brand_result = await db.execute(
            select(
                RunCitation.cited_brand,
                RunCitation.is_target_brand,
                func.count(RunCitation.id).label("count"),
            )
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(CampaignRun.campaign_id == campaign_id)
            .group_by(RunCitation.cited_brand, RunCitation.is_target_brand)
        )
        by_brand = []
        for row in by_brand_result:
            brand_share = row.count / total_citations if total_citations > 0 else 0.0
            by_brand.append({
                "brand": row.cited_brand,
                "share": brand_share,
                "count": row.count,
                "is_target_brand": row.is_target_brand,
            })

        return CitationShareResponse(
            campaign_id=campaign_id,
            overall_citation_share=overall_citation_share,
            total_citations=total_citations,
            target_brand_citations=target_brand_citations,
            by_provider=by_provider,
            by_brand=by_brand,
        )

    @staticmethod
    async def get_campaign_timeseries(
        db: AsyncSession,
        campaign_id: int,
        brand_name: str = "target",
    ) -> TimeseriesResponse:
        """Get citation timeseries for a campaign."""
        # Get completed runs ordered by time
        runs_result = await db.execute(
            select(CampaignRun)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == RunStatus.COMPLETED.value,
            )
            .order_by(CampaignRun.run_number)
        )
        runs = runs_result.scalars().all()

        time_series = []
        for run in runs:
            # Count citations for this run
            total_cit_result = await db.execute(
                select(func.count(RunCitation.id))
                .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
                .where(RunResponse.campaign_run_id == run.id)
            )
            total_citations = total_cit_result.scalar() or 0

            # Count target brand citations
            target_cit_result = await db.execute(
                select(func.count(RunCitation.id))
                .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
                .where(
                    RunResponse.campaign_run_id == run.id,
                    RunCitation.is_target_brand.is_(True),
                )
            )
            brand_citations = target_cit_result.scalar() or 0

            citation_share_overall = (
                brand_citations / total_citations if total_citations > 0 else 0.0
            )

            # By provider for this run
            by_provider_result = await db.execute(
                select(
                    RunResponse.llm_provider,
                    func.count(RunCitation.id).label("total"),
                    func.sum(func.cast(RunCitation.is_target_brand, Integer)).label("target"),
                )
                .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
                .where(RunResponse.campaign_run_id == run.id)
                .group_by(RunResponse.llm_provider)
            )
            citation_share_by_provider = {}
            for row in by_provider_result:
                provider_share = row.target / row.total if row.total > 0 else 0.0
                citation_share_by_provider[row.llm_provider] = provider_share

            time_series.append(
                TimeseriesDataPoint(
                    run_id=run.id,
                    timestamp=run.started_at or run.created_at,
                    citation_share_overall=citation_share_overall,
                    citation_share_by_provider=citation_share_by_provider,
                    total_citations=total_citations,
                    brand_citations=brand_citations,
                )
            )

        return TimeseriesResponse(
            campaign_id=campaign_id,
            brand_name=brand_name,
            time_series=time_series,
            annotations=[],
        )

    @staticmethod
    async def get_brand_ranking(
        db: AsyncSession,
        campaign_id: int,
    ) -> BrandRankingResponse:
        """Get brands ranked by citation frequency."""
        # Total citations
        total_cit_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(CampaignRun.campaign_id == campaign_id)
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
            .where(CampaignRun.campaign_id == campaign_id)
            .group_by(RunCitation.cited_brand, RunCitation.is_target_brand)
            .order_by(func.count(RunCitation.id).desc())
        )

        rankings = []
        rank = 1
        for row in brand_result:
            citation_share = row.count / total_citations if total_citations > 0 else 0.0
            rankings.append(
                BrandRankingItem(
                    rank=rank,
                    brand=row.cited_brand,
                    citation_count=row.count,
                    citation_share=citation_share,
                    is_target_brand=row.is_target_brand,
                )
            )
            rank += 1

        return BrandRankingResponse(
            campaign_id=campaign_id,
            rankings=rankings,
            total_citations=total_citations,
        )

    @staticmethod
    async def get_geo_score_summary(
        db: AsyncSession,
        campaign_id: int,
    ) -> GEOScoreSummaryResponse:
        """Get GEO score summary (placeholder using proxy metrics)."""
        # Overall proxy: avg(citation_count / word_count)
        overall_result = await db.execute(
            select(
                func.avg(
                    func.cast(RunResponse.citation_count, Float) /
                    func.nullif(func.cast(RunResponse.word_count, Float), 0)
                ).label("avg_geo_score"),
                func.count(RunResponse.id).label("total_runs"),
            )
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunResponse.word_count.is_not(None),
                RunResponse.word_count > 0,
            )
        )
        overall_row = overall_result.one_or_none()
        avg_geo_score = overall_row.avg_geo_score or 0.0 if overall_row else 0.0
        total_runs_analyzed = overall_row.total_runs or 0 if overall_row else 0

        # By provider
        by_provider_result = await db.execute(
            select(
                RunResponse.llm_provider,
                func.avg(
                    func.cast(RunResponse.citation_count, Float) /
                    func.nullif(func.cast(RunResponse.word_count, Float), 0)
                ).label("avg_geo_score"),
            )
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunResponse.word_count.is_not(None),
                RunResponse.word_count > 0,
            )
            .group_by(RunResponse.llm_provider)
        )
        by_provider = {}
        for row in by_provider_result:
            by_provider[row.llm_provider] = row.avg_geo_score or 0.0

        return GEOScoreSummaryResponse(
            campaign_id=campaign_id,
            avg_geo_score=avg_geo_score,
            total_runs_analyzed=total_runs_analyzed,
            by_provider=by_provider,
        )

    @staticmethod
    async def get_provider_comparison(
        db: AsyncSession,
        campaign_id: int,
    ) -> ProviderComparisonResponse:
        """Get per-provider comparison metrics."""
        # Aggregate by provider
        provider_result = await db.execute(
            select(
                RunResponse.llm_provider,
                func.count(RunResponse.id).label("total_responses"),
                func.avg(RunResponse.word_count).label("avg_word_count"),
                func.avg(RunResponse.citation_count).label("avg_citation_count"),
                func.avg(RunResponse.latency_ms).label("avg_latency_ms"),
            )
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(CampaignRun.campaign_id == campaign_id)
            .group_by(RunResponse.llm_provider)
        )

        providers = []
        for row in provider_result:
            # Citation share for this provider
            target_cit_result = await db.execute(
                select(
                    func.count(RunCitation.id).label("total"),
                    func.sum(func.cast(RunCitation.is_target_brand, Integer)).label("target"),
                )
                .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
                .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
                .where(
                    CampaignRun.campaign_id == campaign_id,
                    RunResponse.llm_provider == row.llm_provider,
                )
            )
            cit_row = target_cit_result.one_or_none()
            citation_share = 0.0
            if cit_row and cit_row.total and cit_row.total > 0:
                citation_share = (cit_row.target or 0) / cit_row.total

            providers.append(
                ProviderMetrics(
                    provider=row.llm_provider,
                    total_responses=row.total_responses,
                    avg_word_count=row.avg_word_count or 0.0,
                    avg_citation_count=row.avg_citation_count or 0.0,
                    avg_latency_ms=row.avg_latency_ms or 0.0,
                    citation_share=citation_share,
                )
            )

        return ProviderComparisonResponse(
            campaign_id=campaign_id,
            providers=providers,
        )

    @staticmethod
    async def get_campaign_summary(
        db: AsyncSession,
        campaign_id: int,
    ) -> CampaignSummaryResponse:
        """Get campaign summary with counts."""
        # Total runs
        run_count_result = await db.execute(
            select(func.count(CampaignRun.id)).where(
                CampaignRun.campaign_id == campaign_id,
            )
        )
        total_runs = run_count_result.scalar() or 0

        # Total responses
        resp_count_result = await db.execute(
            select(func.count(RunResponse.id))
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(CampaignRun.campaign_id == campaign_id)
        )
        total_responses = resp_count_result.scalar() or 0

        # Total citations (sum of citation_count from run_responses)
        cit_sum_result = await db.execute(
            select(func.coalesce(func.sum(RunResponse.citation_count), 0))
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(CampaignRun.campaign_id == campaign_id)
        )
        total_citations = cit_sum_result.scalar() or 0

        # Latest run
        latest_run_result = await db.execute(
            select(CampaignRun)
            .where(CampaignRun.campaign_id == campaign_id)
            .order_by(CampaignRun.run_number.desc())
            .limit(1)
        )
        latest_run_obj = latest_run_result.scalar_one_or_none()
        latest_run = (
            CampaignRunResponse.model_validate(latest_run_obj)
            if latest_run_obj
            else None
        )

        return CampaignSummaryResponse(
            campaign_id=campaign_id,
            total_runs=total_runs,
            total_responses=total_responses,
            total_citations=total_citations,
            latest_run=latest_run,
            citation_share_by_brand={},  # Phase 4
        )

    @staticmethod
    async def export_campaign_csv_data(
        db: AsyncSession,
        campaign_id: int,
    ) -> list[dict]:
        """Export campaign data for CSV. Returns list of row dicts."""
        # Query all run responses with citations
        # Join: CampaignRun -> RunResponse -> RunCitation -> QueryVersion
        query = (
            select(
                CampaignRun.run_number,
                CampaignRun.started_at,
                RunResponse.llm_provider,
                RunResponse.llm_model,
                RunResponse.word_count,
                RunResponse.citation_count,
                RunResponse.latency_ms,
                QueryVersion.text.label("query_text"),
                RunCitation.cited_brand,
                RunCitation.position_in_response,
                RunCitation.is_target_brand,
                RunCitation.confidence_score,
                RunCitation.citation_span,
            )
            .join(RunResponse, RunResponse.campaign_run_id == CampaignRun.id)
            .join(QueryVersion, QueryVersion.id == RunResponse.query_version_id)
            .outerjoin(RunCitation, RunCitation.run_response_id == RunResponse.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                CampaignRun.status == RunStatus.COMPLETED.value,
            )
            .order_by(CampaignRun.run_number, RunResponse.llm_provider)
        )

        result = await db.execute(query)
        rows = result.all()

        # Convert to list of dicts
        data = []
        for row in rows:
            data.append({
                "run_number": row.run_number,
                "run_date": row.started_at.isoformat() if row.started_at else "",
                "llm_provider": row.llm_provider,
                "llm_model": row.llm_model,
                "query_text": row.query_text,
                "cited_brand": row.cited_brand or "",
                "position_in_response": (
                    row.position_in_response
                    if row.position_in_response is not None
                    else ""
                ),
                "is_target_brand": (
                    row.is_target_brand
                    if row.is_target_brand is not None
                    else ""
                ),
                "confidence_score": (
                    row.confidence_score
                    if row.confidence_score is not None
                    else ""
                ),
                "citation_span": row.citation_span or "",
                "word_count": row.word_count or "",
                "citation_count": row.citation_count or "",
                "latency_ms": row.latency_ms or "",
            })

        return data

    @staticmethod
    async def get_brand_safety_metrics(
        db: AsyncSession,
        campaign_id: int,
    ) -> BrandSafetyMetrics:
        """Get brand safety risk aggregation for a campaign."""
        # Total citations count
        total_cit_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(CampaignRun.campaign_id == campaign_id)
        )
        total_citations = total_cit_result.scalar() or 0

        # Critical: confidence_score < 0.5
        critical_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.confidence_score.is_not(None),
                RunCitation.confidence_score < 0.5,
            )
        )
        critical_count = critical_result.scalar() or 0

        # Warning: 0.5 <= confidence_score < 0.7
        warning_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.confidence_score.is_not(None),
                RunCitation.confidence_score >= 0.5,
                RunCitation.confidence_score < 0.7,
            )
        )
        warning_count = warning_result.scalar() or 0

        # Safe: confidence_score >= 0.7
        safe_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.confidence_score.is_not(None),
                RunCitation.confidence_score >= 0.7,
            )
        )
        safe_count = safe_result.scalar() or 0

        # Unknown: confidence_score IS NULL
        unknown_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.confidence_score.is_(None),
            )
        )
        unknown_count = unknown_result.scalar() or 0

        # Verified count
        verified_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.is_verified.is_(True),
            )
        )
        verified_count = verified_result.scalar() or 0

        # Unverified count
        unverified_result = await db.execute(
            select(func.count(RunCitation.id))
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                RunCitation.is_verified.is_(False),
            )
        )
        unverified_count = unverified_result.scalar() or 0

        # Recent incidents: last 20 citations with confidence < 0.7 OR NULL
        incidents_result = await db.execute(
            select(
                RunCitation.id,
                RunCitation.cited_brand,
                RunCitation.citation_span,
                RunCitation.confidence_score,
                RunCitation.is_verified,
                RunCitation.created_at,
                RunResponse.llm_provider,
            )
            .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .where(
                CampaignRun.campaign_id == campaign_id,
                (
                    RunCitation.confidence_score.is_(None)
                    | (RunCitation.confidence_score < 0.7)
                ),
            )
            .order_by(RunCitation.created_at.desc())
            .limit(20)
        )
        incidents_rows = incidents_result.all()

        recent_incidents = [
            BrandSafetyIncident(
                citation_id=row.id,
                cited_brand=row.cited_brand,
                citation_span=row.citation_span,
                confidence_score=row.confidence_score,
                is_verified=row.is_verified,
                llm_provider=row.llm_provider,
                created_at=row.created_at,
            )
            for row in incidents_rows
        ]

        return BrandSafetyMetrics(
            campaign_id=campaign_id,
            total_citations=total_citations,
            critical_count=critical_count,
            warning_count=warning_count,
            safe_count=safe_count,
            unknown_count=unknown_count,
            verified_count=verified_count,
            unverified_count=unverified_count,
            recent_incidents=recent_incidents,
        )
