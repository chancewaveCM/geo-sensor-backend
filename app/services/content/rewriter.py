"""Content Rewriter service for AI-powered content optimization."""

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.content_rewrite import ContentRewrite, RewriteVariant
from app.prompts.rewrite_prompts import REWRITE_SYSTEM_PROMPT, format_rewrite_prompt
from app.services.llm.factory import LLMFactory


class ContentRewriter:
    """Service for generating AI-powered content rewrites."""

    @staticmethod
    async def generate_rewrites(
        original: str,
        suggestions: list[str],
        brand_voice: str | None,
        provider: str,
        num_variants: int,
        db: AsyncSession,
        workspace_id: int,
    ) -> ContentRewrite:
        """Generate rewrite variants using LLM."""
        api_key = (
            settings.OPENAI_API_KEY if provider == "openai" else settings.GEMINI_API_KEY
        )
        llm = LLMFactory.create(provider, api_key)

        prompt = format_rewrite_prompt(original, suggestions, brand_voice, num_variants)
        response = await llm.generate(
            prompt=prompt,
            system_prompt=REWRITE_SYSTEM_PROMPT,
        )

        variants_text = _parse_variants(response.content, num_variants)

        rewrite = ContentRewrite(
            workspace_id=workspace_id,
            original_content=original,
            suggestion_context="\n".join(suggestions) if suggestions else None,
        )
        db.add(rewrite)
        await db.flush()

        for i, text in enumerate(variants_text, start=1):
            variant = RewriteVariant(
                rewrite_id=rewrite.id,
                variant_number=i,
                content=text,
                status="pending",
            )
            db.add(variant)

        await db.commit()
        await db.refresh(rewrite, ["variants"])
        return rewrite

    @staticmethod
    async def approve_variant(
        variant_id: int,
        rewrite_id: int,
        status: str,
        db: AsyncSession,
    ) -> RewriteVariant:
        """Approve or reject a rewrite variant."""
        variant = await db.get(RewriteVariant, variant_id)
        if not variant:
            raise ValueError(f"Variant {variant_id} not found")

        # Verify variant belongs to the specified rewrite (IDOR protection)
        if variant.rewrite_id != rewrite_id:
            raise ValueError(f"Variant {variant_id} not found for this rewrite")

        variant.status = status
        if status == "approved":
            variant.approved_at = datetime.now(tz=UTC)
        await db.commit()
        await db.refresh(variant)
        return variant

    @staticmethod
    async def get_rewrites(
        workspace_id: int,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ContentRewrite], int]:
        """Get paginated list of rewrites for a workspace."""
        total_result = await db.execute(
            select(func.count(ContentRewrite.id)).where(
                ContentRewrite.workspace_id == workspace_id
            )
        )
        total = total_result.scalar() or 0

        result = await db.execute(
            select(ContentRewrite)
            .where(ContentRewrite.workspace_id == workspace_id)
            .options(selectinload(ContentRewrite.variants))
            .order_by(ContentRewrite.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        rewrites = list(result.scalars().all())
        return rewrites, total

    @staticmethod
    async def get_rewrite(
        rewrite_id: int,
        db: AsyncSession,
    ) -> ContentRewrite | None:
        """Get a specific rewrite with variants."""
        result = await db.execute(
            select(ContentRewrite)
            .where(ContentRewrite.id == rewrite_id)
            .options(selectinload(ContentRewrite.variants))
        )
        return result.scalar_one_or_none()


def _parse_variants(text: str, num_variants: int) -> list[str]:
    """Parse numbered variants from LLM response text."""
    pattern = r"\d+\.\s+"
    parts = re.split(pattern, text)
    variants = [p.strip() for p in parts if p.strip()]
    return variants[:num_variants]


def generate_diff_summary(original: str, rewritten: str) -> str:
    """Generate a simple word-level diff summary."""
    orig_words = set(original.lower().split())
    new_words = set(rewritten.lower().split())
    added = new_words - orig_words
    removed = orig_words - new_words
    parts = []
    if added:
        parts.append(f"+{len(added)} words added")
    if removed:
        parts.append(f"-{len(removed)} words removed")
    return ", ".join(parts) if parts else "No significant changes"
