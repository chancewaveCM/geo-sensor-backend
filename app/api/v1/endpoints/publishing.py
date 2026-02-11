"""Publishing endpoints for SNS platforms."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, WorkspaceMemberDep
from app.models.oauth_token import OAuthPlatform
from app.schemas.publishing import (
    PlatformFormatInfo,
    PublicationListResponse,
    PublicationResponse,
    PublishRequest,
)
from app.services.publishing.base import PublishError
from app.services.publishing.factory import get_publisher
from app.services.publishing.publishing_service import PublishingService

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/publish",
    response_model=PublicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_content(
    workspace_id: int,
    request: PublishRequest,
    member: WorkspaceMemberDep,
    db: DbSession,
):
    """
    Publish content to a social media platform.

    Requires workspace membership and valid OAuth connection for the platform.
    """
    if member.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this workspace",
        )

    service = PublishingService()

    try:
        if request.scheduled_at:
            # Schedule for future
            publication = await service.schedule_publish(
                content=request.content,
                platform=request.platform,
                scheduled_at=request.scheduled_at,
                workspace_id=workspace_id,
                db=db,
            )
        else:
            # Publish immediately
            publication = await service.publish_now(
                content=request.content,
                platform=request.platform,
                workspace_id=workspace_id,
                db=db,
            )

        return publication

    except PublishError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Publishing failed: {str(e)}",
        )


@router.get(
    "/workspaces/{workspace_id}/publications",
    response_model=PublicationListResponse,
)
async def list_publications(
    workspace_id: int,
    member: WorkspaceMemberDep,
    db: DbSession,
    skip: int = 0,
    limit: int = 20,
    platform: str | None = None,
):
    """
    List publications for a workspace.

    Supports pagination and filtering by platform.
    """
    if member.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this workspace",
        )

    service = PublishingService()
    publications, total = await service.get_publications(
        workspace_id=workspace_id,
        db=db,
        skip=skip,
        limit=limit,
        platform_filter=platform,
    )

    return PublicationListResponse(publications=publications, total=total)


@router.get(
    "/workspaces/{workspace_id}/publications/{publication_id}",
    response_model=PublicationResponse,
)
async def get_publication(
    workspace_id: int,
    publication_id: int,
    member: WorkspaceMemberDep,
    db: DbSession,
):
    """Get a specific publication."""
    if member.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this workspace",
        )

    service = PublishingService()
    publication = await service.get_publication(publication_id, db)

    if not publication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Publication not found",
        )

    if publication.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Publication does not belong to this workspace",
        )

    return publication


@router.post(
    "/workspaces/{workspace_id}/publications/{publication_id}/retry",
    response_model=PublicationResponse,
)
async def retry_publication(
    workspace_id: int,
    publication_id: int,
    member: WorkspaceMemberDep,
    db: DbSession,
):
    """Retry a failed publication."""
    if member.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this workspace",
        )

    service = PublishingService()

    # Verify publication exists and belongs to workspace
    publication = await service.get_publication(publication_id, db)
    if not publication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Publication not found",
        )

    if publication.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Publication does not belong to this workspace",
        )

    try:
        publication = await service.retry_failed(publication_id, db)
        return publication
    except PublishError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "/workspaces/{workspace_id}/publish/platforms",
    response_model=list[PlatformFormatInfo],
)
async def get_platform_info(
    workspace_id: int,
    member: WorkspaceMemberDep,
):
    """Get information about supported platforms and their format restrictions."""
    if member.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this workspace",
        )

    platforms = []
    for platform in OAuthPlatform:
        try:
            publisher = get_publisher(platform.value)
            platforms.append(
                PlatformFormatInfo(
                    platform=platform.value,
                    max_length=publisher.max_length,
                    supports_media=publisher.supports_media,
                    supports_threads=publisher.supports_threads,
                )
            )
        except PublishError:
            # Skip unsupported platforms
            continue

    return platforms
