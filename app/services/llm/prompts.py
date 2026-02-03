"""
LLM Prompts
Centralized prompt templates for LLM analysis tasks
"""

# System prompts
SENTIMENT_SYSTEM_PROMPT = "You are a sentiment analysis expert. Respond only in valid JSON."
CONTEXT_SYSTEM_PROMPT = "You are a context classification expert. Respond only in valid JSON."

# Analysis prompts
SENTIMENT_ANALYSIS_PROMPT = '''Analyze the sentiment of the following text{context_part}.

Text: {text}

Respond in JSON format:
{{"sentiment": "positive|neutral|negative", "confidence": 0.0-1.0,
"reasoning": "brief explanation"}}'''

CONTEXT_CLASSIFICATION_PROMPT = '''Classify the context type of how "{brand}" is mentioned.

Text to analyze:

Text: {text}

Context types:
- recommendation: The brand is being recommended or endorsed
- comparison: The brand is being compared with competitors
- mention: Neutral mention of the brand
- negative: Negative context or criticism

Respond in JSON format:
{{"context_type": "recommendation|comparison|mention|negative", "confidence": 0.0-1.0}}'''
