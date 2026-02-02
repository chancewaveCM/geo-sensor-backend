"""
Gemini LLM Provider Implementation
"""

import time
from typing import Optional

from .base import BaseLLMService, LLMProvider, LLMResponse


class GeminiService(BaseLLMService):
    """Google Gemini LLM provider"""

    provider = LLMProvider.GEMINI

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
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
                raise ImportError("google-generativeai package required. Install with: pip install google-generativeai")
        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
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
            tokens_used=response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
            latency_ms=latency_ms,
            raw_response={"candidates": [c.text for c in response.candidates]} if response.candidates else None,
        )

    async def analyze_sentiment(self, text: str, brand_context: Optional[str] = None) -> dict:
        """Analyze sentiment using Gemini"""
        prompt = f'''Analyze the sentiment of the following text{f" regarding {brand_context}" if brand_context else ""}.

Text: {text}

Respond in JSON format:
{{"sentiment": "positive|neutral|negative", "confidence": 0.0-1.0, "reasoning": "brief explanation"}}'''

        response = await self.generate(prompt, temperature=0.3)

        import json
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"sentiment": "neutral", "confidence": 0.5, "reasoning": "Failed to parse response"}

    async def classify_context(self, text: str, brand: str) -> dict:
        """Classify context type for brand mention"""
        prompt = f'''Classify the context type of how "{brand}" is mentioned in the following text.

Text: {text}

Context types:
- recommendation: The brand is being recommended or endorsed
- comparison: The brand is being compared with competitors
- mention: Neutral mention of the brand
- negative: Negative context or criticism

Respond in JSON format:
{{"context_type": "recommendation|comparison|mention|negative", "confidence": 0.0-1.0}}'''

        response = await self.generate(prompt, temperature=0.3)

        import json
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            return {"context_type": "mention", "confidence": 0.5}

    async def health_check(self) -> bool:
        """Check Gemini API availability"""
        try:
            response = await self.generate("Hello", max_tokens=10)
            return len(response.content) > 0
        except Exception:
            return False
