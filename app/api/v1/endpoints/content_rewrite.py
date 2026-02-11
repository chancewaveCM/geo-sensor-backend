"""Content Rewrite API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import WorkspaceMemberDep, get_async_session
from app.schemas.content_rewrite import (
    RewriteListResponse,
    RewriteRequest,
    RewriteResponse,
    RewriteVariantResponse,
    VariantApprovalRequest,
)
from app.services.content.rewriter import ContentRewriter, _generate_diff_summary

router = APIRouter(tags=["content-rewrite"])


@router.post(
    "/workspaces/{workspace_id}/content/rewrite",
    response_model=RewriteResponse,
)
async def generate_rewrite(
    workspace_id: int,
    request: RewriteRequest,
    member: WorkspaceMemberDep,
    db: AsyncSession = Depends(get_async_session),
) -> RewriteResponse:
    """Generate AI-powered content rewrite variants."""
    try:
        rewrite = await ContentRewriter.generate_rewrites(
            original=request.original_content,
            suggestions=request.suggestions,
            brand_voice=request.brand_voice,
            provider=request.llm_provider,
            num_variants=request.num_variants,
            db=db,
            workspace_id=workspace_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rewrite generation failed: {e}")

    return RewriteResponse(
        id=rewrite.id,
        original_content=rewrite.original_content,
        variants=[
            RewriteVariantResponse(
                id=v.id,
                variant_number=v.variant_number,
                content=v.content,
                status=v.status,
                diff_summary=_generate_diff_summary(rewrite.original_content, v.content),
            )
            for v in rewrite.variants
        ],
        created_at=rewrite.created_at,
    )


@router.get(
    "/workspaces/{workspace_id}/content/rewrites",
    response_model=RewriteListResponse,
)
async def list_rewrites(
    workspace_id: int,
    member: WorkspaceMemberDep,
    db: AsyncSession = Depends(get_async_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> RewriteListResponse:
    """List content rewrites for a workspace."""
    rewrites, total = await ContentRewriter.get_rewrites(workspace_id, db, skip, limit)
    return RewriteListResponse(
        rewrites=[
            RewriteResponse(
                id=r.id,
                original_content=r.original_content,
                variants=[
                    RewriteVariantResponse(
                        id=v.id,
                        variant_number=v.variant_number,
                        content=v.content,
                        status=v.status,
                        diff_summary=_generate_diff_summary(r.original_content, v.content),
                    )
                    for v in r.variants
                ],
                created_at=r.created_at,
            )
            for r in rewrites
        ],
        total=total,
    )


@router.get(
    "/workspaces/{workspace_id}/content/rewrites/{rewrite_id}",
    response_model=RewriteResponse,
)
async def get_rewrite(
    workspace_id: int,
    rewrite_id: int,
    member: WorkspaceMemberDep,
    db: AsyncSession = Depends(get_async_session),
) -> RewriteResponse:
    """Get a specific content rewrite with variants."""
    rewrite = await ContentRewriter.get_rewrite(rewrite_id, db)
    if not rewrite or rewrite.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Rewrite not found")

    return RewriteResponse(
        id=rewrite.id,
        original_content=rewrite.original_content,
        variants=[
            RewriteVariantResponse(
                id=v.id,
                variant_number=v.variant_number,
                content=v.content,
                status=v.status,
                diff_summary=_generate_diff_summary(rewrite.original_content, v.content),
            )
            for v in rewrite.variants
        ],
        created_at=rewrite.created_at,
    )


@router.patch(
    "/workspaces/{workspace_id}/content/rewrites/{rewrite_id}/variants/{variant_id}",
    response_model=RewriteVariantResponse,
)
async def update_variant_status(
    workspace_id: int,
    rewrite_id: int,
    variant_id: int,
    request: VariantApprovalRequest,
    member: WorkspaceMemberDep,
    db: AsyncSession = Depends(get_async_session),
) -> RewriteVariantResponse:
    """Approve or reject a rewrite variant."""
    rewrite = await ContentRewriter.get_rewrite(rewrite_id, db)
    if not rewrite or rewrite.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Rewrite not found")

    try:
        variant = await ContentRewriter.approve_variant(variant_id, request.status, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return RewriteVariantResponse(
        id=variant.id,
        variant_number=variant.variant_number,
        content=variant.content,
        status=variant.status,
        diff_summary=_generate_diff_summary(rewrite.original_content, variant.content),
    )
