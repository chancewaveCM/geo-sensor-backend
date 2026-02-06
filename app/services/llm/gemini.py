"""
Gemini LLM Provider Implementation
"""

import logging
import time

from .base import BaseLLMService, LLMProvider, LLMResponse
from .constants import CLASSIFICATION_TEMPERATURE, DEFAULT_MAX_TOKENS, HEALTH_CHECK_MAX_TOKENS
from .prompts import (
    CONTEXT_CLASSIFICATION_PROMPT,
    SENTIMENT_ANALYSIS_PROMPT,
    SENTIMENT_SYSTEM_PROMPT,
)
from .utils import parse_llm_json_response

logger = logging.getLogger(__name__)


class GeminiService(BaseLLMService):
    """Google Gemini LLM provider"""

    provider = LLMProvider.GEMINI

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy initialization of Gemini client"""
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai.GenerativeModel(self.model)
            except ImportError:
                raise ImportError(
                    "google-generativeai package required. "
                    "Install with: pip install google-generativeai"
                )
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResponse:
        """Generate response using Gemini"""
        start_time = time.time()

        client = self._get_client()

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        response = await client.generate_content_async(
            full_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
        )

        latency_ms = (time.time() - start_time) * 1000

        return LLMResponse(
            content=response.text,
            provider=self.provider,
            model=self.model,
            tokens_used=(
                response.usage_metadata.total_token_count
                if hasattr(response, 'usage_metadata') else 0
            ),
            latency_ms=latency_ms,
            raw_response=(
                {"candidates": [c.text for c in response.candidates]}
                if response.candidates else None
            ),
        )

    async def analyze_sentiment(self, text: str, brand_context: str | None = None) -> dict:
        """Analyze sentiment using Gemini"""
        context_part = f" regarding {brand_context}" if brand_context else ""
        prompt = SENTIMENT_ANALYSIS_PROMPT.format(context_part=context_part, text=text)

        # Gemini uses system prompt in the prompt itself
        full_prompt = f"{SENTIMENT_SYSTEM_PROMPT}\n\n{prompt}"

        response = await self.generate(full_prompt, temperature=CLASSIFICATION_TEMPERATURE)

        return parse_llm_json_response(
            content=response.content,
            required_keys=["sentiment", "confidence"],
            fallback={"sentiment": "neutral", "confidence": 0.5, "reasoning": "Parse error"},
            logger=logger,
        )

    async def classify_context(self, text: str, brand: str) -> dict:
        """Classify context type for brand mention"""
        prompt = CONTEXT_CLASSIFICATION_PROMPT.format(brand=brand, text=text)

        response = await self.generate(prompt, temperature=CLASSIFICATION_TEMPERATURE)

        return parse_llm_json_response(
            content=response.content,
            required_keys=["context_type"],
            fallback={"context_type": "mention", "confidence": 0.5},
            logger=logger,
        )

    async def health_check(self) -> bool:
        """Check Gemini API availability"""
        try:
            response = await self.generate("Hello", max_tokens=HEALTH_CHECK_MAX_TOKENS)
            return len(response.content) > 0
        except Exception as e:
            logger.warning(f"Gemini health check failed: {e}")
            return False
