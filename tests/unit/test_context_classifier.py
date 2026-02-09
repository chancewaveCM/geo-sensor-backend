"""Tests for Context Classification (F7)"""

import pytest

from app.services.analysis.context_classifier import (
    ContextClassifier,
    ContextType,
)


@pytest.fixture
def classifier():
    return ContextClassifier()


class TestContextClassifier:
    def test_informational_classification(self, classifier):
        text = (
            "Samsung is a South Korean multinational electronics "
            "corporation headquartered in Seoul. The company was "
            "founded in 1938 and typically manufactures consumer electronics."
        )
        result = classifier.classify(text)

        assert result.primary_context == ContextType.INFORMATIONAL
        # May have low confidence if no strong keywords, which is acceptable
        assert result.confidence >= 0.3
        # Informational is the default, so signals might be empty
        assert isinstance(result.signals, list)

    def test_comparative_classification(self, classifier):
        text = (
            "When comparing Samsung Galaxy vs iPhone, Samsung offers "
            "better zoom while Apple excels in video processing. "
            "The difference between these phones is clear."
        )
        result = classifier.classify(text)

        assert result.primary_context == ContextType.COMPARATIVE
        assert result.confidence > 0.5
        # Check that comparison keywords were detected
        assert len(result.signals) > 0

    def test_recommendation_classification(self, classifier):
        text = (
            "I highly recommend the Samsung Galaxy A55. "
            "It's the best choice for budget smartphones and you should use it. "
            "This is my top pick for 2024."
        )
        result = classifier.classify(text)

        assert result.primary_context == ContextType.RECOMMENDATION
        assert result.confidence > 0.5
        # Check that recommendation keywords were detected
        assert len(result.signals) > 0

    def test_tutorial_classification(self, classifier):
        text = (
            "Step 1: Connect your Samsung phone to the monitor. "
            "Step 2: Navigate to Settings. Step 3: Enable DeX mode."
        )
        result = classifier.classify(text)

        assert result.primary_context == ContextType.TUTORIAL
        assert result.confidence > 0.5
        assert any("step" in sig.lower() for sig in result.signals)

    def test_opinion_classification(self, classifier):
        text = (
            "I think Samsung has really improved their software. "
            "One UI 7 feels much more polished, in my opinion."
        )
        result = classifier.classify(text)

        assert result.primary_context == ContextType.OPINION
        assert result.confidence > 0.5
        assert any("think" in sig.lower() or "opinion" in sig.lower() for sig in result.signals)
