"""
LLM Service Constants
Centralized configuration for LLM providers
"""

# Temperature settings
# Low temperature for deterministic classification tasks
CLASSIFICATION_TEMPERATURE = 0.3

# Standard temperature for creative generation
DEFAULT_TEMPERATURE = 0.7

# Token limits
DEFAULT_MAX_TOKENS = 1024
HEALTH_CHECK_MAX_TOKENS = 10

# Default models per provider
DEFAULT_MODELS = {
    "gemini": "gemini-1.5-flash",
    "openai": "gpt-4o-mini",
}
