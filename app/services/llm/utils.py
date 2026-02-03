"""
LLM Utilities
Shared utility functions for LLM providers
"""

import json
import logging


def parse_llm_json_response(
    content: str,
    required_keys: list[str],
    fallback: dict,
    logger: logging.Logger,
) -> dict:
    """
    Parse and validate LLM JSON response with fallback.

    Args:
        content: Raw LLM response content
        required_keys: Keys that must be present in the response
        fallback: Default response if parsing fails
        logger: Logger instance for warnings

    Returns:
        Parsed dict or fallback on failure
    """
    try:
        result = json.loads(content)

        # Validate required keys
        if not all(k in result for k in required_keys):
            raise ValueError(f"Missing required keys: {required_keys}")

        # Normalize confidence to 0-1 range if present
        if "confidence" in result:
            conf = result.get("confidence", 0.5)
            if not isinstance(conf, (int, float)) or not (0 <= conf <= 1):
                result["confidence"] = 0.5

        return result
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning(f"Invalid LLM response: {e}")
        return fallback
