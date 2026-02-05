"""Retry handler with exponential backoff."""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_delay_ms: int = 500
    max_delay_ms: int = 10000
    exponential_base: float = 2.0


class RetryHandler:
    """Handle retries with exponential backoff."""

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()

    async def execute_with_retry(
        self,
        operation: Callable[[], Coroutine[Any, Any, T]],
        operation_name: str = "operation",
    ) -> T:
        """
        Execute an operation with retry logic.

        Args:
            operation: Async callable to execute
            operation_name: Name for logging

        Returns:
            Result of the operation

        Raises:
            Last exception if all retries exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await operation()
            except Exception as e:
                last_exception = e

                if not self._should_retry(e, attempt):
                    raise

                delay_ms = self._calculate_delay(attempt)
                logger.warning(
                    f"{operation_name} failed (attempt {attempt + 1}/"
                    f"{self.config.max_retries + 1}): {e}. "
                    f"Retrying in {delay_ms}ms..."
                )

                await asyncio.sleep(delay_ms / 1000)

        # Should never reach here, but just in case
        raise last_exception or Exception("Retry exhausted with no exception")

    def _should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if error is retryable."""
        if attempt >= self.config.max_retries:
            return False

        # Add more sophisticated retry logic here if needed
        # For now, retry on all exceptions except specific ones
        non_retryable = (ValueError, TypeError, KeyError)
        return not isinstance(error, non_retryable)

    def _calculate_delay(self, attempt: int) -> int:
        """Calculate exponential backoff delay in milliseconds."""
        delay = self.config.initial_delay_ms * (
            self.config.exponential_base**attempt
        )
        return min(int(delay), self.config.max_delay_ms)
