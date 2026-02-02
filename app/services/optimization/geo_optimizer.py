"""
GEO Optimization Analyzer
F9: Analyze brand performance and generate GEO optimization recommendations
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

from ..analysis.brand_matcher import BrandMatch
from ..analysis.citation_share import CitationShareResult
from ..analysis.context_classifier import ContextType, ContextClassification
from ..analysis.sentiment_analyzer import SentimentResult


class OptimizationPriority(Enum):
    """Priority level for optimization actions"""
    CRITICAL = "critical"    # 0-20% citation share
    HIGH = "high"            # 20-40% citation share
    MEDIUM = "medium"        # 40-60% citation share
    LOW = "low"              # 60-80% citation share
    MAINTAIN = "maintain"    # 80-100% citation share


class OptimizationType(Enum):
    """Type of optimization recommendation"""
    VISIBILITY = "visibility"              # Increase brand mentions
    SENTIMENT = "sentiment"                # Improve sentiment score
    CONTEXT = "context"                    # Target better contexts
    COMPETITIVE = "competitive"            # Counter competitors
    CONTENT = "content"                    # Content strategy
    TECHNICAL = "technical"                # Technical SEO/GEO


@dataclass
class OptimizationAction:
    """Single optimization recommendation"""
    type: OptimizationType
    priority: OptimizationPriority
    title: str
    description: str
    expected_impact: str  # "citation_share +5-10%"
    effort: str           # "low|medium|high"
    metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "expected_impact": self.expected_impact,
            "effort": self.effort,
            "metrics": self.metrics,
        }


@dataclass
class BrandPerformance:
    """Performance metrics for a single brand"""
    brand_id: int
    brand_name: str
    citation_share: float
    mention_count: int
    avg_sentiment: float
    sentiment_distribution: Dict[str, int]
    context_distribution: Dict[str, int]
    primary_contexts: List[ContextType]

    def to_dict(self) -> dict:
        return {
            "brand_id": self.brand_id,
            "brand_name": self.brand_name,
            "citation_share": round(self.citation_share, 2),
            "mention_count": self.mention_count,
            "avg_sentiment": round(self.avg_sentiment, 3),
            "sentiment_distribution": self.sentiment_distribution,
            "context_distribution": self.context_distribution,
            "primary_contexts": [c.value for c in self.primary_contexts],
        }


@dataclass
class GEOAnalysis:
    """Complete GEO optimization analysis"""
    brand_performance: BrandPerformance
    optimization_actions: List[OptimizationAction]
    competitive_insights: Dict[str, any]
    overall_score: float  # 0-100
    query_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "brand_performance": self.brand_performance.to_dict(),
            "optimization_actions": [a.to_dict() for a in self.optimization_actions],
            "competitive_insights": self.competitive_insights,
            "overall_score": round(self.overall_score, 1),
            "query_id": self.query_id,
        }


class GEOOptimizer:
    """
    Analyze brand citation performance and generate optimization recommendations

    Analysis dimensions:
    - Citation share (visibility)
    - Sentiment distribution (brand perception)
    - Context types (mention quality)
    - Competitive positioning
    """

    def analyze(
        self,
        brand_id: int,
        citation_result: CitationShareResult,
        matches: List[BrandMatch],
        sentiments: Optional[List[SentimentResult]] = None,
        contexts: Optional[List[ContextClassification]] = None,
        query_id: Optional[int] = None,
    ) -> GEOAnalysis:
        """
        Generate GEO optimization analysis for a brand

        Args:
            brand_id: Target brand ID
            citation_result: Citation share results
            matches: Brand matches from BrandMatcher
            sentiments: Optional sentiment analysis results
            contexts: Optional context classifications
            query_id: Optional query ID for tracking

        Returns:
            GEOAnalysis with performance metrics and recommendations
        """
        # Find brand performance
        brand_share = None
        for share in citation_result.shares:
            if share.brand_id == brand_id:
                brand_share = share
                break

        if not brand_share:
            # Brand not mentioned
            return self._generate_no_mention_analysis(
                brand_id=brand_id,
                total_mentions=citation_result.total_mentions,
                query_id=query_id,
            )

        # Calculate sentiment distribution
        sentiment_dist = {"positive": 0, "neutral": 0, "negative": 0}
        avg_sentiment = 0.0

        if sentiments:
            brand_sentiments = [
                s for s in sentiments if hasattr(s, 'brand_id') and s.brand_id == brand_id
            ]
            for sent in brand_sentiments:
                sentiment_dist[sent.sentiment.value] += 1
                # Convert sentiment to numeric: positive=1, neutral=0, negative=-1
                sentiment_map = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}
                sentiment_val = sentiment_map[sent.sentiment.value]
                avg_sentiment += sentiment_val
            if brand_sentiments:
                avg_sentiment /= len(brand_sentiments)

        # Calculate context distribution
        context_dist = {}
        primary_contexts = []

        if contexts:
            brand_contexts = [c for c in contexts if c.confidence > 0.5]
            for ctx in brand_contexts:
                ctx_type = ctx.primary_context.value
                context_dist[ctx_type] = context_dist.get(ctx_type, 0) + 1

            # Top 3 contexts
            sorted_contexts = sorted(context_dist.items(), key=lambda x: x[1], reverse=True)
            primary_contexts = [ContextType(ctx[0]) for ctx in sorted_contexts[:3]]

        # Build performance profile
        performance = BrandPerformance(
            brand_id=brand_id,
            brand_name=brand_share.brand_name,
            citation_share=brand_share.share_percentage,
            mention_count=brand_share.mention_count,
            avg_sentiment=avg_sentiment,
            sentiment_distribution=sentiment_dist,
            context_distribution=context_dist,
            primary_contexts=primary_contexts,
        )

        # Generate optimization actions
        actions = self._generate_recommendations(performance, citation_result)

        # Competitive insights
        competitive = self._analyze_competitors(brand_share, citation_result)

        # Overall GEO score (0-100)
        score = self._calculate_geo_score(performance)

        return GEOAnalysis(
            brand_performance=performance,
            optimization_actions=actions,
            competitive_insights=competitive,
            overall_score=score,
            query_id=query_id,
        )

    def _generate_no_mention_analysis(
        self,
        brand_id: int,
        total_mentions: int,
        query_id: Optional[int],
    ) -> GEOAnalysis:
        """Generate analysis for brands with zero mentions"""
        performance = BrandPerformance(
            brand_id=brand_id,
            brand_name="Unknown",
            citation_share=0.0,
            mention_count=0,
            avg_sentiment=0.0,
            sentiment_distribution={"positive": 0, "neutral": 0, "negative": 0},
            context_distribution={},
            primary_contexts=[],
        )

        actions = [
            OptimizationAction(
                type=OptimizationType.VISIBILITY,
                priority=OptimizationPriority.CRITICAL,
                title="Establish GEO Presence",
                description="Brand has zero visibility in AI responses. Immediate action required.",
                expected_impact="citation_share 0% → 5-15%",
                effort="high",
                metrics={"current_share": 0.0, "target_share": 10.0},
            ),
            OptimizationAction(
                type=OptimizationType.CONTENT,
                priority=OptimizationPriority.CRITICAL,
                title="Create Authoritative Content",
                description=(
                    "Publish high-quality, structured content that AI models can reference."
                ),
                expected_impact="citation_share +5-10%",
                effort="high",
            ),
        ]

        return GEOAnalysis(
            brand_performance=performance,
            optimization_actions=actions,
            competitive_insights={
                "total_competitors": total_mentions,
                "market_dominated_by_others": True,
            },
            overall_score=0.0,
            query_id=query_id,
        )

    def _generate_recommendations(
        self,
        performance: BrandPerformance,
        citation_result: CitationShareResult,
    ) -> List[OptimizationAction]:
        """Generate optimization recommendations based on performance"""
        actions = []

        # Priority based on citation share
        priority = self._get_priority(performance.citation_share)

        # 1. Visibility optimization
        if performance.citation_share < 50:
            actions.append(OptimizationAction(
                type=OptimizationType.VISIBILITY,
                priority=priority,
                title="Increase Brand Mentions",
                description=(
                    f"Current citation share: {performance.citation_share:.1f}%. Target: 50%+"
                ),
                expected_impact=f"citation_share +{max(5, 50 - performance.citation_share):.0f}%",
                effort="medium" if performance.citation_share > 20 else "high",
                metrics={"current_share": performance.citation_share, "target_share": 50.0},
            ))

        # 2. Sentiment optimization
        if performance.avg_sentiment < 0.3:
            priority = (
                OptimizationPriority.HIGH if performance.avg_sentiment < 0
                else OptimizationPriority.MEDIUM
            )
            actions.append(OptimizationAction(
                type=OptimizationType.SENTIMENT,
                priority=priority,
                title="Improve Brand Sentiment",
                description=(
                    f"Average sentiment score: {performance.avg_sentiment:.2f}. "
                    "Address negative mentions."
                ),
                expected_impact="sentiment +0.2-0.5",
                effort="medium",
                metrics={"current_sentiment": performance.avg_sentiment, "target_sentiment": 0.5},
            ))

        # 3. Context optimization
        if ContextType.RECOMMENDATION not in performance.primary_contexts:
            actions.append(OptimizationAction(
                type=OptimizationType.CONTEXT,
                priority=OptimizationPriority.MEDIUM,
                title="Target Recommendation Contexts",
                description=(
                    "Brand not appearing in recommendation contexts. "
                    "Focus on 'best for' scenarios."
                ),
                expected_impact="recommendation_contexts +20-30%",
                effort="medium",
                metrics={"recommendation_context_share": 0.0},
            ))

        # 4. Competitive positioning
        top_competitor_share = (
            citation_result.shares[0].share_percentage if citation_result.shares else 0
        )
        if top_competitor_share - performance.citation_share > 20:
            actions.append(OptimizationAction(
                type=OptimizationType.COMPETITIVE,
                priority=OptimizationPriority.HIGH,
                title="Counter Top Competitor",
                description=(
                    f"Top competitor has "
                    f"{top_competitor_share - performance.citation_share:.1f}% higher share."
                ),
                expected_impact=(
                    f"citation_share +"
                    f"{(top_competitor_share - performance.citation_share) / 2:.0f}%"
                ),
                effort="high",
                metrics={"gap": top_competitor_share - performance.citation_share},
            ))

        # Sort by priority
        priority_order = {
            OptimizationPriority.CRITICAL: 0,
            OptimizationPriority.HIGH: 1,
            OptimizationPriority.MEDIUM: 2,
            OptimizationPriority.LOW: 3,
            OptimizationPriority.MAINTAIN: 4,
        }
        actions.sort(key=lambda a: priority_order[a.priority])

        return actions

    def _analyze_competitors(
        self,
        brand_share,
        citation_result: CitationShareResult,
    ) -> Dict[str, any]:
        """Analyze competitive landscape"""
        competitors = [s for s in citation_result.shares if s.brand_id != brand_share.brand_id]

        rank = 1
        for i, share in enumerate(citation_result.shares):
            if share.brand_id == brand_share.brand_id:
                rank = i + 1
                break

        return {
            "rank": rank,
            "total_competitors": len(competitors),
            "top_competitor": competitors[0].brand_name if competitors else None,
            "top_competitor_share": competitors[0].share_percentage if competitors else 0.0,
            "share_gap": (
                (competitors[0].share_percentage - brand_share.share_percentage)
                if competitors else 0.0
            ),
            "market_leader": rank == 1,
        }

    def _calculate_geo_score(self, performance: BrandPerformance) -> float:
        """
        Calculate overall GEO performance score (0-100)

        Weights:
        - Citation share: 50%
        - Sentiment: 25%
        - Context quality: 25%
        """
        # Citation score (0-50)
        citation_score = min(performance.citation_share * 0.5, 50.0)

        # Sentiment score (0-25): map [-1, 1] to [0, 25]
        sentiment_score = (performance.avg_sentiment + 1) * 12.5

        # Context score (0-25): recommendation contexts are best
        context_score = 0.0
        if performance.primary_contexts:
            weights = {
                ContextType.RECOMMENDATION: 25.0,
                ContextType.COMPARATIVE: 20.0,
                ContextType.TUTORIAL: 15.0,
                ContextType.INFORMATIONAL: 10.0,
                ContextType.OPINION: 5.0,
            }
            context_score = weights.get(performance.primary_contexts[0], 0.0)

        return min(citation_score + sentiment_score + context_score, 100.0)

    def _get_priority(self, citation_share: float) -> OptimizationPriority:
        """Determine priority based on citation share"""
        if citation_share < 20:
            return OptimizationPriority.CRITICAL
        elif citation_share < 40:
            return OptimizationPriority.HIGH
        elif citation_share < 60:
            return OptimizationPriority.MEDIUM
        elif citation_share < 80:
            return OptimizationPriority.LOW
        else:
            return OptimizationPriority.MAINTAIN
