"""
Analysis Services Module
Brand matching, sentiment analysis, context classification, citation share, and evaluation
"""

from .brand_matcher import BrandMatcher, BrandMatch, Brand, MatchType
from .sentiment import SentimentAnalyzer, SentimentResult, SentimentType
from .context_classifier import ContextClassifier, ContextClassification, ContextType
from .citation_share import CitationShareCalculator, CitationShare, CitationShareResult
from .evaluator import Evaluator, EvaluationResult, EvaluationMetrics, GroundTruthEntry

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
