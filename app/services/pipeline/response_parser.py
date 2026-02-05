"""JSON response parsing utilities for pipeline."""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def extract_json_from_response(content: str) -> Any:
    """
    Extract JSON from LLM response, handling markdown code blocks.

    Handles:
    - Plain JSON
    - ```json ... ``` blocks
    - ``` ... ``` blocks
    """
    # Try to find JSON in code blocks first
    code_block_pattern = r"```(?:json)?\s*([\s\S]*?)```"
    matches = re.findall(code_block_pattern, content)

    if matches:
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # Try parsing the entire content as JSON
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        pass

    # Try to find JSON array or object in the content
    json_pattern = r"(\[[\s\S]*\]|\{[\s\S]*\})"
    matches = re.findall(json_pattern, content)

    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    raise ValueError(f"Could not extract JSON from response: {content[:200]}...")


def parse_categories_response(
    content: str, expected_count: int
) -> list[dict[str, str]]:
    """
    Parse category generation response.

    Returns:
        List of {"name": str, "description": str}
    """
    try:
        data = extract_json_from_response(content)
    except ValueError as e:
        logger.error(f"Failed to parse categories: {e}")
        raise

    if not isinstance(data, list):
        raise ValueError(f"Expected list, got {type(data)}")

    categories = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = item.get("name", "").strip()
        description = item.get("description", "").strip()
        if name:
            categories.append({"name": name[:255], "description": description})

    if len(categories) < expected_count:
        logger.warning(f"Got {len(categories)} categories, expected {expected_count}")

    return categories[:expected_count]


def parse_queries_response(content: str, expected_count: int) -> list[str]:
    """
    Parse query expansion response.

    Returns:
        List of query strings
    """
    try:
        data = extract_json_from_response(content)
    except ValueError as e:
        logger.error(f"Failed to parse queries: {e}")
        raise

    if not isinstance(data, list):
        raise ValueError(f"Expected list, got {type(data)}")

    queries = []
    seen = set()

    for item in data:
        if not isinstance(item, str):
            continue
        query = item.strip()
        query_lower = query.lower()

        # Skip empty or duplicate queries
        if not query or len(query) < 10 or query_lower in seen:
            continue

        queries.append(query)
        seen.add(query_lower)

        if len(queries) >= expected_count:
            break

    if len(queries) < expected_count:
        logger.warning(f"Got {len(queries)} queries, expected {expected_count}")

    return queries[:expected_count]
