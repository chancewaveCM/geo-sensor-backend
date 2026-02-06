"""Gallery endpoints for browsing, labeling, and reviewing LLM responses."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import (
    CurrentUser,
    DbSession,
    Pagination,
    WorkspaceAdminDep,
    WorkspaceMemberDep,
)
from app.models.campaign import (
    Campaign,
    CampaignRun,
    RunResponse,
)
from app.models.gallery import CitationReview, ResponseLabel
from app.models.run_citation import RunCitation
from app.schemas.gallery import (
    CitationReviewCreate,
    CitationReviewResponse,
    GalleryDetailResponse,
    GalleryRunResponseItem,
    ResponseLabelCreate,
    ResponseLabelResponse,
)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/gallery",
    tags=["gallery"],
)


# ---------------------------------------------------------------------------
# Gallery List
# ---------------------------------------------------------------------------


@router.get("/responses", response_model=list[GalleryRunResponseItem])
async def list_gallery_responses(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
    pagination: Pagination,
    llm_provider: str | None = None,
    query_type: str | None = None,
    campaign_id: int | None = None,
    has_flags: bool | None = None,
) -> list[GalleryRunResponseItem]:
    """List run responses in gallery view with filters."""
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
    query = query.offset(pagination.skip).limit(pagination.limit)

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


@router.get("/responses/{response_id}", response_model=GalleryDetailResponse)
async def get_gallery_response_detail(
    db: DbSession,
    workspace_id: int,
    response_id: int,
    member: WorkspaceMemberDep,
) -> GalleryDetailResponse:
    """Get detailed view of a run response with labels and citations."""
    # Verify response belongs to workspace
    result = await db.execute(
        select(RunResponse)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .join(Campaign, CampaignRun.campaign_id == Campaign.id)
        .where(
            RunResponse.id == response_id,
            Campaign.workspace_id == workspace_id,
        )
    )
    response = result.scalar_one_or_none()
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Response not found in this workspace",
        )

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

    detail = GalleryDetailResponse.model_validate(response)
    detail.labels = [ResponseLabelResponse.model_validate(label) for label in labels]
    detail.citations = [
        {
            "id": c.id,
            "cited_brand": c.cited_brand,
            "citation_span": c.citation_span,
            "context_before": c.context_before,
            "context_after": c.context_after,
            "position_in_response": c.position_in_response,
            "is_target_brand": c.is_target_brand,
            "confidence_score": c.confidence_score,
            "is_verified": c.is_verified,
        }
        for c in citations
    ]

    return detail


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


@router.post(
    "/labels",
    response_model=ResponseLabelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_response_label(
    db: DbSession,
    workspace_id: int,
    current_user: CurrentUser,
    label_in: ResponseLabelCreate,
    member: WorkspaceMemberDep,
) -> ResponseLabelResponse:
    """Add a label to a run response. Requires workspace membership."""
    # Verify the run_response belongs to this workspace
    rr_result = await db.execute(
        select(RunResponse)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .join(Campaign, CampaignRun.campaign_id == Campaign.id)
        .where(
            RunResponse.id == label_in.run_response_id,
            Campaign.workspace_id == workspace_id,
        )
    )
    if rr_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run response not found in this workspace",
        )

    try:
        label = ResponseLabel(
            workspace_id=workspace_id,
            run_response_id=label_in.run_response_id,
            label_type=label_in.label_type,
            label_key=label_in.label_key,
            label_value=label_in.label_value,
            severity=label_in.severity,
            created_by=current_user.id,
        )
        db.add(label)
        await db.commit()
        await db.refresh(label)
        return ResponseLabelResponse.model_validate(label)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create label: {e!s}",
        )


@router.get("/labels", response_model=list[ResponseLabelResponse])
async def list_response_labels(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
    response_id: int | None = None,
    label_type: str | None = None,
    unresolved_only: bool = False,
) -> list[ResponseLabelResponse]:
    """List labels in the workspace. Filter by response_id, type, resolved status."""
    query = select(ResponseLabel).where(ResponseLabel.workspace_id == workspace_id)

    if response_id is not None:
        query = query.where(ResponseLabel.run_response_id == response_id)
    if label_type is not None:
        query = query.where(ResponseLabel.label_type == label_type)
    if unresolved_only:
        query = query.where(ResponseLabel.resolved_at.is_(None))

    query = query.order_by(ResponseLabel.created_at.desc())
    result = await db.execute(query)
    labels = result.scalars().all()
    return [ResponseLabelResponse.model_validate(label) for label in labels]


@router.post("/labels/{label_id}/resolve", response_model=ResponseLabelResponse)
async def resolve_label(
    db: DbSession,
    workspace_id: int,
    label_id: int,
    current_user: CurrentUser,
    admin: WorkspaceAdminDep,
) -> ResponseLabelResponse:
    """Resolve a label. Requires ADMIN role."""
    result = await db.execute(
        select(ResponseLabel).where(
            ResponseLabel.id == label_id,
            ResponseLabel.workspace_id == workspace_id,
        )
    )
    label = result.scalar_one_or_none()
    if label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label not found",
        )

    if label.resolved_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Label is already resolved",
        )

    try:
        label.resolved_at = datetime.now(tz=UTC)
        label.resolved_by = current_user.id
        await db.commit()
        await db.refresh(label)
        return ResponseLabelResponse.model_validate(label)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve label: {e!s}",
        )


@router.delete("/labels/{label_id}", status_code=status.HTTP_200_OK)
async def delete_label(
    db: DbSession,
    workspace_id: int,
    label_id: int,
    admin: WorkspaceAdminDep,
) -> dict[str, str]:
    """Delete a label. Requires ADMIN role."""
    result = await db.execute(
        select(ResponseLabel).where(
            ResponseLabel.id == label_id,
            ResponseLabel.workspace_id == workspace_id,
        )
    )
    label = result.scalar_one_or_none()
    if label is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Label not found",
        )

    try:
        await db.delete(label)
        await db.commit()
        return {"message": "Label deleted"}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete label: {e!s}",
        )


# ---------------------------------------------------------------------------
# Citation Reviews
# ---------------------------------------------------------------------------


@router.post(
    "/citation-reviews",
    response_model=CitationReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_citation_review(
    db: DbSession,
    workspace_id: int,
    current_user: CurrentUser,
    review_in: CitationReviewCreate,
    member: WorkspaceMemberDep,
) -> CitationReviewResponse:
    """Review a citation (mark as false positive, etc.). Requires membership."""
    # Verify citation belongs to workspace
    cit_result = await db.execute(
        select(RunCitation)
        .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .join(Campaign, CampaignRun.campaign_id == Campaign.id)
        .where(
            RunCitation.id == review_in.run_citation_id,
            Campaign.workspace_id == workspace_id,
        )
    )
    if cit_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation not found in this workspace",
        )

    try:
        review = CitationReview(
            run_citation_id=review_in.run_citation_id,
            review_type=review_in.review_type,
            reviewer_comment=review_in.reviewer_comment,
            created_by=current_user.id,
        )
        db.add(review)
        await db.commit()
        await db.refresh(review)
        return CitationReviewResponse.model_validate(review)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create citation review: {e!s}",
        )


@router.get("/citation-reviews", response_model=list[CitationReviewResponse])
async def list_citation_reviews(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
    citation_id: int | None = None,
    review_type: str | None = None,
) -> list[CitationReviewResponse]:
    """List citation reviews. Filter by citation_id and review_type."""
    # Build query via join to ensure workspace isolation
    query = (
        select(CitationReview)
        .join(RunCitation, CitationReview.run_citation_id == RunCitation.id)
        .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .join(Campaign, CampaignRun.campaign_id == Campaign.id)
        .where(Campaign.workspace_id == workspace_id)
    )

    if citation_id is not None:
        query = query.where(CitationReview.run_citation_id == citation_id)
    if review_type is not None:
        query = query.where(CitationReview.review_type == review_type)

    query = query.order_by(CitationReview.created_at.desc())
    result = await db.execute(query)
    reviews = result.scalars().all()
    return [CitationReviewResponse.model_validate(r) for r in reviews]


@router.patch(
    "/citations/{citation_id}/verify",
    status_code=status.HTTP_200_OK,
)
async def toggle_citation_verification(
    db: DbSession,
    workspace_id: int,
    citation_id: int,
    current_user: CurrentUser,
    admin: WorkspaceAdminDep,
) -> dict:
    """Toggle citation verification status. Requires ADMIN role."""
    # Verify citation belongs to workspace
    cit_result = await db.execute(
        select(RunCitation)
        .join(RunResponse, RunCitation.run_response_id == RunResponse.id)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .join(Campaign, CampaignRun.campaign_id == Campaign.id)
        .where(
            RunCitation.id == citation_id,
            Campaign.workspace_id == workspace_id,
        )
    )
    citation = cit_result.scalar_one_or_none()
    if citation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Citation not found in this workspace",
        )

    try:
        # Toggle verification
        citation.is_verified = not citation.is_verified
        if citation.is_verified:
            citation.verified_by = current_user.id
            citation.verified_at = datetime.now(tz=UTC)
        else:
            citation.verified_by = None
            citation.verified_at = None

        await db.commit()
        await db.refresh(citation)

        return {
            "id": citation.id,
            "is_verified": citation.is_verified,
            "verified_by": citation.verified_by,
            "verified_at": str(citation.verified_at) if citation.verified_at else None,
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update citation verification: {e!s}",
        )


# ---------------------------------------------------------------------------
# Inline Comparisons
# ---------------------------------------------------------------------------


@router.get("/compare/llm")
async def compare_by_llm(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
    run_id: int = Query(..., description="Campaign run ID"),
    query_version_id: int = Query(..., description="Query version ID"),
) -> dict:
    """Compare responses from different LLMs for the same query in a run."""
    from app.services.campaign.comparison_engine import ComparisonEngine

    # Get responses for this query in this run
    result = await db.execute(
        select(RunResponse)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .join(Campaign, CampaignRun.campaign_id == Campaign.id)
        .where(
            RunResponse.campaign_run_id == run_id,
            RunResponse.query_version_id == query_version_id,
            Campaign.workspace_id == workspace_id,
        )
        .order_by(RunResponse.llm_provider)
    )
    responses = result.scalars().all()

    if len(responses) < 2:
        return {
            "comparison_type": "llm_vs_llm",
            "responses": [
                {
                    "id": r.id,
                    "llm_provider": r.llm_provider,
                    "content": r.content,
                    "word_count": r.word_count,
                    "citation_count": r.citation_count,
                }
                for r in responses
            ],
            "diff": None,
            "message": "Need at least 2 responses to compare",
        }

    # Fetch citations for all responses
    citations_result = await db.execute(
        select(RunCitation)
        .where(RunCitation.run_response_id.in_([r.id for r in responses]))
        .order_by(RunCitation.run_response_id, RunCitation.position_in_response)
    )
    all_citations = citations_result.scalars().all()

    # Group citations by response_id
    citations_by_response = {}
    for citation in all_citations:
        if citation.run_response_id not in citations_by_response:
            citations_by_response[citation.run_response_id] = []
        citations_by_response[citation.run_response_id].append(citation)

    # Use ComparisonEngine for pairwise comparison
    engine = ComparisonEngine()
    comparisons = []
    for i in range(len(responses)):
        for j in range(i + 1, len(responses)):
            r1, r2 = responses[i], responses[j]
            cit1 = citations_by_response.get(r1.id, [])
            cit2 = citations_by_response.get(r2.id, [])

            diff = engine.compute_diff_summary(r1, r2, cit1, cit2)
            comparisons.append({
                "response_a": {"id": r1.id, "llm_provider": r1.llm_provider},
                "response_b": {"id": r2.id, "llm_provider": r2.llm_provider},
                "similarity": diff.content_similarity,
                "brand_overlap": diff.citation_overlap_ratio,
                "shared_brands": diff.shared_brands,
                "unique_a": diff.left_only_brands,
                "unique_b": diff.right_only_brands,
            })

    return {
        "comparison_type": "llm_vs_llm",
        "run_id": run_id,
        "query_version_id": query_version_id,
        "responses": [
            {
                "id": r.id,
                "llm_provider": r.llm_provider,
                "word_count": r.word_count,
                "citation_count": r.citation_count,
            }
            for r in responses
        ],
        "comparisons": comparisons,
    }


@router.get("/compare/date")
async def compare_by_date(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
    campaign_id: int = Query(..., description="Campaign ID"),
    query_version_id: int = Query(..., description="Query version ID"),
    llm_provider: str = Query(..., description="LLM provider name"),
    run_id_a: int = Query(..., description="First run ID"),
    run_id_b: int = Query(..., description="Second run ID"),
) -> dict:
    """Compare the same query+LLM across two different runs (dates)."""
    from app.services.campaign.comparison_engine import ComparisonEngine

    # Get response A
    result_a = await db.execute(
        select(RunResponse)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .join(Campaign, CampaignRun.campaign_id == Campaign.id)
        .where(
            RunResponse.campaign_run_id == run_id_a,
            RunResponse.query_version_id == query_version_id,
            RunResponse.llm_provider == llm_provider,
            Campaign.workspace_id == workspace_id,
        )
    )
    response_a = result_a.scalar_one_or_none()

    # Get response B
    result_b = await db.execute(
        select(RunResponse)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .join(Campaign, CampaignRun.campaign_id == Campaign.id)
        .where(
            RunResponse.campaign_run_id == run_id_b,
            RunResponse.query_version_id == query_version_id,
            RunResponse.llm_provider == llm_provider,
            Campaign.workspace_id == workspace_id,
        )
    )
    response_b = result_b.scalar_one_or_none()

    if response_a is None or response_b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both responses not found",
        )

    # Fetch citations
    citations_a_result = await db.execute(
        select(RunCitation)
        .where(RunCitation.run_response_id == response_a.id)
        .order_by(RunCitation.position_in_response)
    )
    citations_a = citations_a_result.scalars().all()

    citations_b_result = await db.execute(
        select(RunCitation)
        .where(RunCitation.run_response_id == response_b.id)
        .order_by(RunCitation.position_in_response)
    )
    citations_b = citations_b_result.scalars().all()

    engine = ComparisonEngine()
    diff = engine.compute_diff_summary(response_a, response_b, citations_a, citations_b)

    return {
        "comparison_type": "date_vs_date",
        "llm_provider": llm_provider,
        "response_a": {
            "id": response_a.id,
            "run_id": run_id_a,
            "word_count": response_a.word_count,
            "citation_count": response_a.citation_count,
            "content": response_a.content,
        },
        "response_b": {
            "id": response_b.id,
            "run_id": run_id_b,
            "word_count": response_b.word_count,
            "citation_count": response_b.citation_count,
            "content": response_b.content,
        },
        "diff": {
            "similarity": diff.content_similarity,
            "brand_overlap": diff.citation_overlap_ratio,
            "content_changed": diff.content_similarity < 0.95,
            "shared_brands": diff.shared_brands,
            "unique_a": diff.left_only_brands,
            "unique_b": diff.right_only_brands,
        },
    }


@router.get("/compare/version")
async def compare_by_version(
    db: DbSession,
    workspace_id: int,
    member: WorkspaceMemberDep,
    run_id: int = Query(..., description="Campaign run ID"),
    llm_provider: str = Query(..., description="LLM provider"),
    query_version_id_a: int = Query(..., description="First query version ID"),
    query_version_id_b: int = Query(..., description="Second query version ID"),
) -> dict:
    """Compare responses for two different query versions in the same run."""
    from app.services.campaign.comparison_engine import ComparisonEngine

    result_a = await db.execute(
        select(RunResponse)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .join(Campaign, CampaignRun.campaign_id == Campaign.id)
        .where(
            RunResponse.campaign_run_id == run_id,
            RunResponse.query_version_id == query_version_id_a,
            RunResponse.llm_provider == llm_provider,
            Campaign.workspace_id == workspace_id,
        )
    )
    response_a = result_a.scalar_one_or_none()

    result_b = await db.execute(
        select(RunResponse)
        .join(CampaignRun, RunResponse.campaign_run_id == CampaignRun.id)
        .join(Campaign, CampaignRun.campaign_id == Campaign.id)
        .where(
            RunResponse.campaign_run_id == run_id,
            RunResponse.query_version_id == query_version_id_b,
            RunResponse.llm_provider == llm_provider,
            Campaign.workspace_id == workspace_id,
        )
    )
    response_b = result_b.scalar_one_or_none()

    if response_a is None or response_b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both responses not found",
        )

    # Fetch citations
    citations_a_result = await db.execute(
        select(RunCitation)
        .where(RunCitation.run_response_id == response_a.id)
        .order_by(RunCitation.position_in_response)
    )
    citations_a = citations_a_result.scalars().all()

    citations_b_result = await db.execute(
        select(RunCitation)
        .where(RunCitation.run_response_id == response_b.id)
        .order_by(RunCitation.position_in_response)
    )
    citations_b = citations_b_result.scalars().all()

    engine = ComparisonEngine()
    diff = engine.compute_diff_summary(response_a, response_b, citations_a, citations_b)

    return {
        "comparison_type": "version_vs_version",
        "run_id": run_id,
        "llm_provider": llm_provider,
        "response_a": {
            "id": response_a.id,
            "query_version_id": query_version_id_a,
            "word_count": response_a.word_count,
            "citation_count": response_a.citation_count,
            "content": response_a.content,
        },
        "response_b": {
            "id": response_b.id,
            "query_version_id": query_version_id_b,
            "word_count": response_b.word_count,
            "citation_count": response_b.citation_count,
            "content": response_b.content,
        },
        "diff": {
            "similarity": diff.content_similarity,
            "brand_overlap": diff.citation_overlap_ratio,
            "content_changed": diff.content_similarity < 0.95,
            "shared_brands": diff.shared_brands,
            "unique_a": diff.left_only_brands,
            "unique_b": diff.right_only_brands,
        },
    }
