"""Comparison engine for Gallery feature."""

import logging
from dataclasses import dataclass

from app.models.campaign import RunResponse
from app.models.run_citation import RunCitation

logger = logging.getLogger(__name__)


@dataclass
class DiffSummary:
    """Summary of differences between two responses."""

    shared_brands: list[str]
    left_only_brands: list[str]
    right_only_brands: list[str]
    content_similarity: float
    citation_overlap_ratio: float


class ComparisonEngine:
    """Compare LLM responses for Gallery."""

    def compute_diff_summary(
        self,
        left: RunResponse,
        right: RunResponse,
        left_citations: list[RunCitation],
        right_citations: list[RunCitation],
    ) -> DiffSummary:
        """Compute diff summary between two responses."""
        left_brands = {c.cited_brand for c in left_citations}
        right_brands = {c.cited_brand for c in right_citations}

        return DiffSummary(
            shared_brands=sorted(left_brands & right_brands),
            left_only_brands=sorted(left_brands - right_brands),
            right_only_brands=sorted(right_brands - left_brands),
            content_similarity=self._compute_similarity(left.content, right.content),
            citation_overlap_ratio=self._compute_overlap(left_brands, right_brands),
        )

    def _compute_similarity(self, text_a: str, text_b: str) -> float:
        """Jaccard similarity between word sets."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union) if union else 0.0

    def _compute_overlap(
        self, brands_a: set[str], brands_b: set[str]
    ) -> float:
        """Brand citation overlap ratio."""
        if not brands_a and not brands_b:
            return 1.0
        if not brands_a or not brands_b:
            return 0.0
        intersection = brands_a & brands_b
        union = brands_a | brands_b
        return len(intersection) / len(union) if union else 0.0
