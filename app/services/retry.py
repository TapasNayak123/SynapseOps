"""Exponential backoff retry decorator for transient failures."""
from __future__ import annotations

import time
import random
import logging
import functools
from typing import Tuple, Type

logger = logging.getLogger(__name__)

# Default transient exception types
_DEFAULT_RETRYABLE: Tuple[Type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable_exceptions: Tuple[Type[BaseException], ...] = _DEFAULT_RETRYABLE,
    on_retry=None,
):
    """Decorator that retries a function with exponential backoff + jitter.

    Args:
        max_retries: Maximum number of retry attempts (total calls = max_retries + 1).
        base_delay: Initial delay in seconds before first retry.
        max_delay: Cap on delay between retries.
        retryable_exceptions: Tuple of exception types that trigger a retry.
        on_retry: Optional callback(attempt, exception, delay) called before each retry sleep.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt == max_retries:
                        logger.error(
                            "retry_exhausted: %s failed after %d attempts: %s",
                            func.__name__, max_retries + 1, exc,
                        )
                        raise
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, base_delay), max_delay)
                    if on_retry:
                        on_retry(attempt + 1, exc, delay)
                    logger.warning(
                        "retry: %s attempt %d/%d failed (%s), retrying in %.1fs",
                        func.__name__, attempt + 1, max_retries + 1, exc, delay,
                    )
                    time.sleep(delay)
            raise last_exc  # unreachable but satisfies type checkers
        return wrapper
    return decorator
