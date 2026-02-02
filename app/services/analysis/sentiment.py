"""
Sentiment Analyzer
F6: Gemini-based sentiment analysis with rule-based fallback
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..llm.base import BaseLLMService


class SentimentType(Enum):
    """Sentiment classification"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


@dataclass
class SentimentResult:
    """Sentiment analysis result"""
    sentiment: SentimentType
    confidence: float  # 0.0 - 1.0
    reasoning: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "sentiment": self.sentiment.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


class SentimentAnalyzer:
    """
    Sentiment analyzer with LLM and rule-based fallback

    Supports Korean and English text.
    Uses LLM when available, falls back to rule-based for reliability.
    """

    # Rule-based sentiment words
    POSITIVE_WORDS_EN = {
        "best", "excellent", "great", "amazing", "fantastic", "outstanding",
        "recommend", "love", "perfect", "superior", "innovative", "reliable",
        "top", "leading", "trusted", "quality", "exceptional", "impressive",
    }

    NEGATIVE_WORDS_EN = {
        "worst", "terrible", "bad", "poor", "awful", "disappointing",
        "avoid", "hate", "broken", "inferior", "unreliable", "overpriced",
        "cheap", "faulty", "defective", "problem", "issue", "fail",
    }

    POSITIVE_WORDS_KO = {
        "최고", "훌륭", "좋은", "뛰어난", "추천", "사랑", "완벽",
        "우수", "혁신", "신뢰", "품질", "만족", "굿", "베스트",
    }

    NEGATIVE_WORDS_KO = {
        "최악", "나쁜", "별로", "실망", "피하", "싫", "고장",
        "불량", "문제", "비싸", "저렴", "후회", "안좋",
    }

    def __init__(self, llm_service: Optional["BaseLLMService"] = None):
        """
        Args:
            llm_service: Optional LLM service for advanced analysis
        """
        self.llm_service = llm_service

    async def analyze(
        self,
        text: str,
        brand_context: Optional[str] = None,
        use_llm: bool = True,
    ) -> SentimentResult:
        """
        Analyze sentiment of text

        Args:
            text: Text to analyze
            brand_context: Optional brand name for context
            use_llm: Whether to use LLM (falls back to rules if unavailable)

        Returns:
            SentimentResult with sentiment, confidence, and reasoning
        """
        # Try LLM first if available and requested
        if use_llm and self.llm_service:
            try:
                result = await self._llm_analyze(text, brand_context)
                if result:
                    return result
            except Exception:
                pass  # Fall back to rule-based

        # Rule-based fallback
        return self._rule_based_analyze(text, brand_context)

    async def _llm_analyze(
        self,
        text: str,
        brand_context: Optional[str],
    ) -> Optional[SentimentResult]:
        """Use LLM for sentiment analysis"""
        if not self.llm_service:
            return None

        result = await self.llm_service.analyze_sentiment(text, brand_context)

        sentiment_str = result.get("sentiment", "neutral").lower()
        try:
            sentiment = SentimentType(sentiment_str)
        except ValueError:
            sentiment = SentimentType.NEUTRAL

        return SentimentResult(
            sentiment=sentiment,
            confidence=float(result.get("confidence", 0.5)),
            reasoning=result.get("reasoning"),
        )

    def _rule_based_analyze(
        self,
        text: str,
        brand_context: Optional[str],
    ) -> SentimentResult:
        """Rule-based sentiment analysis fallback"""
        text_lower = text.lower()

        # Count sentiment words
        positive_count = 0
        negative_count = 0

        # English words
        for word in self.POSITIVE_WORDS_EN:
            if word in text_lower:
                positive_count += 1

        for word in self.NEGATIVE_WORDS_EN:
            if word in text_lower:
                negative_count += 1

        # Korean words
        for word in self.POSITIVE_WORDS_KO:
            if word in text:
                positive_count += 1

        for word in self.NEGATIVE_WORDS_KO:
            if word in text:
                negative_count += 1

        # Determine sentiment
        total = positive_count + negative_count

        if total == 0:
            return SentimentResult(
                sentiment=SentimentType.NEUTRAL,
                confidence=0.5,
                reasoning="No sentiment indicators found (rule-based)",
            )

        positive_ratio = positive_count / total

        if positive_ratio > 0.6:
            sentiment = SentimentType.POSITIVE
            confidence = min(0.9, 0.5 + positive_ratio * 0.4)
        elif positive_ratio < 0.4:
            sentiment = SentimentType.NEGATIVE
            confidence = min(0.9, 0.5 + (1 - positive_ratio) * 0.4)
        else:
            sentiment = SentimentType.NEUTRAL
            confidence = 0.6

        return SentimentResult(
            sentiment=sentiment,
            confidence=confidence,
            reasoning=(
                f"Rule-based: {positive_count} positive, {negative_count} negative indicators"
            ),
        )

    def analyze_sync(
        self,
        text: str,
        brand_context: Optional[str] = None,
    ) -> SentimentResult:
        """Synchronous rule-based analysis (for testing)"""
        return self._rule_based_analyze(text, brand_context)
