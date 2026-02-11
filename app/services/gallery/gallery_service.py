"""Gallery service - comparison and filtering logic."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign, CampaignRun, RunResponse
from app.models.gallery import ResponseLabel
from app.models.run_citation import RunCitation
from app.schemas.gallery import GalleryRunResponseItem


class GalleryService:
    """Service for gallery-related business logic."""

    @staticmethod
    async def list_gallery_responses_with_filters(
        db: AsyncSession,
        workspace_id: int,
        skip: int,
        limit: int,
        llm_provider: str | None = None,
        campaign_id: int | None = None,
        has_flags: bool | None = None,
    ) -> list[GalleryRunResponseItem]:
        """List run responses in gallery view with filters and counts."""
        # Base query: RunResponse -> CampaignRun -> Campaign (workspace filter)
        query = (
            select(RunResponse)
            .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
            .join(Campaign, CampaignRun.campaign_id == Campaign.id)
            .where(Campaign.workspace_id == workspace_id)
        )

        # Apply filters
        if llm_provider is not None:
            query = query.where(RunResponse.llm_provider == llm_provider)
        if campaign_id is not None:
            query = query.where(Campaign.id == campaign_id)

        query = query.order_by(RunResponse.created_at.desc())
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        responses = result.scalars().all()

        items = []
        for resp in responses:
            # Count labels
            label_count_result = await db.execute(
                select(func.count(ResponseLabel.id)).where(
                    ResponseLabel.run_response_id == resp.id,
                )
            )
            label_count = label_count_result.scalar() or 0

            # Check flags
            flag_result = await db.execute(
                select(func.count(ResponseLabel.id)).where(
                    ResponseLabel.run_response_id == resp.id,
                    ResponseLabel.label_type == "flag",
                    ResponseLabel.resolved_at.is_(None),
                )
            )
            flag_count = flag_result.scalar() or 0

            if has_flags is True and flag_count == 0:
                continue
            if has_flags is False and flag_count > 0:
                continue

            item = GalleryRunResponseItem.model_validate(resp)
            item.label_count = label_count
            item.has_flags = flag_count > 0
            items.append(item)

        return items

    @staticmethod
    async def get_response_detail_with_relations(
        db: AsyncSession,
        response_id: int,
    ) -> tuple[RunResponse, list, list]:
        """
        Get response with labels and citations.

        Returns:
            Tuple of (response, labels, citations)
        """
        # Fetch labels
        labels_result = await db.execute(
            select(ResponseLabel)
            .where(ResponseLabel.run_response_id == response_id)
            .order_by(ResponseLabel.created_at.desc())
        )
        labels = labels_result.scalars().all()

        # Fetch citations
        citations_result = await db.execute(
            select(RunCitation)
            .where(RunCitation.run_response_id == response_id)
            .order_by(RunCitation.position_in_response)
        )
        citations = citations_result.scalars().all()

        return labels, citations
