"""
Analysis Services Module
Brand matching, sentiment analysis, context classification, citation share, and evaluation
"""

from .brand_matcher import Brand, BrandMatch, BrandMatcher, MatchType
from .citation_share import CitationShare, CitationShareCalculator, CitationShareResult
from .context_classifier import ContextClassification, ContextClassifier, ContextType
from .evaluator import EvaluationMetrics, EvaluationResult, Evaluator, GroundTruthEntry
from .sentiment import SentimentAnalyzer, SentimentResult, SentimentType

__all__ = [
    # Brand Matching (F5)
    "BrandMatcher",
    "BrandMatch",
    "Brand",
    "MatchType",
    # Sentiment (F6)
    "SentimentAnalyzer",
    "SentimentResult",
    "SentimentType",
    # Context (F7)
    "ContextClassifier",
    "ContextClassification",
    "ContextType",
    # Citation Share (F8)
    "CitationShareCalculator",
    "CitationShare",
    "CitationShareResult",
    # Evaluator (F16)
    "Evaluator",
    "EvaluationResult",
    "EvaluationMetrics",
    "GroundTruthEntry",
]
