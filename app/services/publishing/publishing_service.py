"""Publishing service for managing SNS publications."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.publication import Publication, PublishQueue
from app.services.oauth.oauth_service import OAuthService
from app.services.publishing.base import PublishError
from app.services.publishing.factory import get_publisher


class PublishingService:
    """Service for managing SNS publications."""

    def __init__(self):
        self.oauth_service = OAuthService()

    async def publish_now(
        self, content: str, platform: str, workspace_id: int, db: AsyncSession
    ) -> Publication:
        """
        Publish content immediately to a platform.

        Args:
            content: Content to publish
            platform: Platform identifier
            workspace_id: Workspace ID
            db: Database session

        Returns:
            Publication record

        Raises:
            PublishError: If publishing fails
        """
        # Get publisher
        publisher = get_publisher(platform)

        # Validate content
        errors = publisher.validate_content(content)
        if errors:
            raise PublishError(f"Content validation failed: {', '.join(errors)}")

        # Create publication record
        publication = Publication(
            workspace_id=workspace_id,
            content=content,
            platform=platform,
            status="draft",
        )
        db.add(publication)
        await db.commit()
        await db.refresh(publication)

        try:
            # Get valid OAuth token
            token = await self.oauth_service.get_valid_token(platform, workspace_id, db)

            # Publish to platform
            result = await publisher.publish(content, token)

            # Update publication with success
            publication.status = "published"
            publication.published_at = datetime.now(tz=UTC)
            publication.external_id = result.get("external_id")
            await db.commit()
            await db.refresh(publication)

        except Exception as e:
            # Update publication with failure
            publication.status = "failed"
            publication.error_message = str(e)
            await db.commit()
            await db.refresh(publication)

            # Add to retry queue
            queue_entry = PublishQueue(
                publication_id=publication.id,
                retry_count=0,
                max_retries=3,
            )
            db.add(queue_entry)
            await db.commit()

            raise

        return publication

    async def schedule_publish(
        self,
        content: str,
        platform: str,
        scheduled_at: datetime,
        workspace_id: int,
        db: AsyncSession,
    ) -> Publication:
        """
        Schedule content for future publication.

        Args:
            content: Content to publish
            platform: Platform identifier
            scheduled_at: When to publish
            workspace_id: Workspace ID
            db: Database session

        Returns:
            Publication record
        """
        # Get publisher to validate
        publisher = get_publisher(platform)

        # Validate content
        errors = publisher.validate_content(content)
        if errors:
            raise PublishError(f"Content validation failed: {', '.join(errors)}")

        # Create scheduled publication
        publication = Publication(
            workspace_id=workspace_id,
            content=content,
            platform=platform,
            status="scheduled",
            scheduled_at=scheduled_at,
        )
        db.add(publication)
        await db.commit()
        await db.refresh(publication)

        return publication

    async def get_publications(
        self,
        workspace_id: int,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        platform_filter: str | None = None,
    ) -> tuple[list[Publication], int]:
        """
        Get publications for a workspace.

        Args:
            workspace_id: Workspace ID
            db: Database session
            skip: Offset for pagination
            limit: Max results
            platform_filter: Optional platform filter

        Returns:
            Tuple of (publications, total count)
        """
        # Build query
        query = select(Publication).where(Publication.workspace_id == workspace_id)

        if platform_filter:
            query = query.where(Publication.platform == platform_filter)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await db.execute(count_query)
        total = count_result.scalar() or 0

        # Get paginated results
        query = query.order_by(Publication.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        publications = list(result.scalars().all())

        return publications, total

    async def get_publication(self, publication_id: int, db: AsyncSession) -> Publication | None:
        """
        Get a publication by ID.

        Args:
            publication_id: Publication ID
            db: Database session

        Returns:
            Publication or None if not found
        """
        stmt = select(Publication).where(Publication.id == publication_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def retry_failed(self, publication_id: int, db: AsyncSession) -> Publication:
        """
        Retry a failed publication.

        Args:
            publication_id: Publication ID
            db: Database session

        Returns:
            Updated publication

        Raises:
            PublishError: If publication not found or not failed
        """
        # Get publication
        publication = await self.get_publication(publication_id, db)
        if not publication:
            raise PublishError("Publication not found")

        if publication.status != "failed":
            raise PublishError(f"Cannot retry publication with status: {publication.status}")

        # Get queue entry
        queue_stmt = select(PublishQueue).where(PublishQueue.publication_id == publication_id)
        queue_result = await db.execute(queue_stmt)
        queue_entry = queue_result.scalar_one_or_none()

        if queue_entry and queue_entry.retry_count >= queue_entry.max_retries:
            raise PublishError("Maximum retries exceeded")

        try:
            # Get publisher and token
            publisher = get_publisher(publication.platform)
            token = await self.oauth_service.get_valid_token(
                publication.platform, publication.workspace_id, db
            )

            # Retry publish
            result = await publisher.publish(publication.content, token)

            # Update publication with success
            publication.status = "published"
            publication.published_at = datetime.now(tz=UTC)
            publication.external_id = result.get("external_id")
            publication.error_message = None

            # Remove from queue
            if queue_entry:
                await db.delete(queue_entry)

            await db.commit()
            await db.refresh(publication)

        except Exception as e:
            # Update retry count
            if queue_entry:
                queue_entry.retry_count += 1
            else:
                queue_entry = PublishQueue(
                    publication_id=publication.id,
                    retry_count=1,
                    max_retries=3,
                )
                db.add(queue_entry)

            publication.error_message = str(e)
            await db.commit()
            await db.refresh(publication)

            raise

        return publication
