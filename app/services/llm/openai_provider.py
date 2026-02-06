"""
OpenAI LLM Provider Implementation
"""

import logging
import time

from .base import BaseLLMService, LLMProvider, LLMResponse
from .constants import CLASSIFICATION_TEMPERATURE, DEFAULT_MAX_TOKENS, HEALTH_CHECK_MAX_TOKENS
from .prompts import (
    CONTEXT_CLASSIFICATION_PROMPT,
    CONTEXT_SYSTEM_PROMPT,
    SENTIMENT_ANALYSIS_PROMPT,
    SENTIMENT_SYSTEM_PROMPT,
)
from .utils import parse_llm_json_response

logger = logging.getLogger(__name__)


class OpenAIService(BaseLLMService):
    """OpenAI LLM provider"""

    provider = LLMProvider.OPENAI

    # Models that do NOT support temperature/top_p/logprobs
    # (only gpt-5.2 with reasoning.effort=none supports them)
    _NO_TEMPERATURE_MODELS = {
        "gpt-5-nano", "gpt-5-mini", "gpt-5", "gpt-5.1",
    }

    def __init__(self, api_key: str, model: str = "gpt-5-nano"):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy initialization of OpenAI client"""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai package required. Install with: pip install openai")
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResponse:
        """Generate response using OpenAI"""
        start_time = time.time()

        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Build request params — filter unsupported params by model
        request_params: dict = {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }

        # gpt-5-nano/mini/5/5.1 don't support temperature
        supports_temp = self.model not in self._NO_TEMPERATURE_MODELS
        if supports_temp and temperature != 1.0:
            request_params["temperature"] = temperature

        response = await client.chat.completions.create(
            **request_params
        )

        latency_ms = (time.time() - start_time) * 1000

        return LLMResponse(
            content=response.choices[0].message.content or "",
            provider=self.provider,
            model=self.model,
            tokens_used=response.usage.total_tokens if response.usage else 0,
            latency_ms=latency_ms,
            raw_response=response.model_dump() if hasattr(response, 'model_dump') else None,
        )

    async def analyze_sentiment(self, text: str, brand_context: str | None = None) -> dict:
        """Analyze sentiment using OpenAI"""
        context_part = f" regarding {brand_context}" if brand_context else ""
        prompt = SENTIMENT_ANALYSIS_PROMPT.format(context_part=context_part, text=text)

        response = await self.generate(
            prompt,
            system_prompt=SENTIMENT_SYSTEM_PROMPT,
            temperature=CLASSIFICATION_TEMPERATURE,
        )

        return parse_llm_json_response(
            content=response.content,
            required_keys=["sentiment", "confidence"],
            fallback={"sentiment": "neutral", "confidence": 0.5, "reasoning": "Parse error"},
            logger=logger,
        )

    async def classify_context(self, text: str, brand: str) -> dict:
        """Classify context type for brand mention"""
        prompt = CONTEXT_CLASSIFICATION_PROMPT.format(brand=brand, text=text)

        response = await self.generate(
            prompt,
            system_prompt=CONTEXT_SYSTEM_PROMPT,
            temperature=CLASSIFICATION_TEMPERATURE,
        )

        return parse_llm_json_response(
            content=response.content,
            required_keys=["context_type"],
            fallback={"context_type": "mention", "confidence": 0.5},
            logger=logger,
        )

    async def health_check(self) -> bool:
        """Check OpenAI API availability"""
        try:
            response = await self.generate("Hello", max_tokens=HEALTH_CHECK_MAX_TOKENS)
            return len(response.content) > 0
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False
