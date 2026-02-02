"""
OpenAI LLM Provider Implementation
"""

import time
from typing import Optional

from .base import BaseLLMService, LLMProvider, LLMResponse


class OpenAIService(BaseLLMService):
    """OpenAI LLM provider"""

    provider = LLMProvider.OPENAI

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
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
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Generate response using OpenAI"""
        start_time = time.time()

        client = self._get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
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

    async def analyze_sentiment(self, text: str, brand_context: Optional[str] = None) -> dict:
        """Analyze sentiment using OpenAI"""
        system = "You are a sentiment analysis expert. Respond only in valid JSON."
        prompt = f'''Analyze the sentiment of the following text{f" regarding {brand_context}" if brand_context else ""}.

Text: {text}

Respond in JSON format:
{{"sentiment": "positive|neutral|negative", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}'''

        response = await self.generate(prompt, system_prompt=system, temperature=0.3)

        import json
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"sentiment": "neutral", "confidence": 0.5, "reasoning": "Failed to parse response"}

    async def classify_context(self, text: str, brand: str) -> dict:
        """Classify context type for brand mention"""
        system = "You are a context classification expert. Respond only in valid JSON."
        prompt = f'''Classify the context type of how "{brand}" is mentioned in the following text.

Text: {text}

Context types:
- recommendation: The brand is being recommended or endorsed
- comparison: The brand is being compared with competitors
- mention: Neutral mention of the brand
- negative: Negative context or criticism

Respond in JSON format:
{{"context_type": "recommendation|comparison|mention|negative", "confidence": 0.0-1.0}}'''

        response = await self.generate(prompt, system_prompt=system, temperature=0.3)

        import json
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"context_type": "mention", "confidence": 0.5}

    async def health_check(self) -> bool:
        """Check OpenAI API availability"""
        try:
            response = await self.generate("Hello", max_tokens=10)
            return len(response.content) > 0
        except Exception:
            return False
