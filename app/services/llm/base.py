"""
LLM Service Base Interface
F4: LLM Service with Gemini + OpenAI providers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.enums import LLMProvider


@dataclass
class LLMResponse:
    """Response from LLM provider"""
    content: str
    provider: LLMProvider
    model: str
    tokens_used: int
    latency_ms: float
    raw_response: dict | None = None


class BaseLLMService(ABC):
    """Abstract base class for LLM providers"""

    provider: LLMProvider
    model: str

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Generate a response from the LLM"""
        pass

    @abstractmethod
    async def analyze_sentiment(self, text: str, brand_context: str | None = None) -> dict:
        """
        Analyze sentiment of text regarding a brand
        Returns: {"sentiment": "positive|neutral|negative", "confidence": 0.0-1.0, "reasoning": str}
        """
        pass

    @abstractmethod
    async def classify_context(self, text: str, brand: str) -> dict:
        """
        Classify the context type of a brand mention
        Returns:
            {"context_type": "recommendation|comparison|mention|negative", "confidence": 0.0-1.0}
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the LLM service is available"""
        pass
