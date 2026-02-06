"""Tests for Sentiment Analyzer (F6)"""

import pytest

from app.services.analysis.sentiment import SentimentAnalyzer, SentimentType


@pytest.fixture
def analyzer():
    return SentimentAnalyzer()


class TestSentimentAnalyzer:
    def test_positive_sentiment(self, analyzer):
        text = "This is the best product ever! I love it, excellent quality!"
        result = analyzer.analyze_sync(text)

        assert result.sentiment == SentimentType.POSITIVE
        assert result.confidence > 0.5

    def test_negative_sentiment(self, analyzer):
        text = "Terrible product, worst experience. Very disappointing and poor quality."
        result = analyzer.analyze_sync(text)

        assert result.sentiment == SentimentType.NEGATIVE
        assert result.confidence > 0.5

    def test_neutral_sentiment(self, analyzer):
        text = "The device has a screen and a battery."
        result = analyzer.analyze_sync(text)

        assert result.sentiment == SentimentType.NEUTRAL

    def test_korean_positive(self, analyzer):
        text = "최고의 품질! 정말 좋은 제품이에요. 추천합니다!"
        result = analyzer.analyze_sync(text)

        assert result.sentiment == SentimentType.POSITIVE

    def test_korean_negative(self, analyzer):
        text = "최악의 제품. 문제가 많고 실망스럽습니다."
        result = analyzer.analyze_sync(text)

        assert result.sentiment == SentimentType.NEGATIVE

    def test_result_to_dict(self, analyzer):
        result = analyzer.analyze_sync("Great product!")
        d = result.to_dict()

        assert "sentiment" in d
        assert "confidence" in d
        assert "reasoning" in d
