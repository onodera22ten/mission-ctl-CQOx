# backend/resilience/retry.py
"""
Retry Strategy with Exponential Backoff
AWS Best Practice for transient failure handling
"""
import time
import random
from typing import Callable, Any, Type, Tuple
from functools import wraps
import asyncio

def exponential_backoff_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Exponential backoff retry decorator

    AWS Best Practice:
    - Exponential backoff: delay = min(base_delay * (exponential_base ** attempt), max_delay)
    - Jitter: Add randomness to prevent thundering herd
    - Only retry on specific exceptions

    Args:
        max_attempts: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Add random jitter to delay
        exceptions: Tuple of exceptions to retry on
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        # Last attempt failed, raise exception
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    # Add jitter (random variation)
                    if jitter:
                        delay *= (0.5 + random.random())

                    print(f"[Retry] Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                          f"Retrying in {delay:.2f}s...")

                    time.sleep(delay)

            # Should never reach here
            raise last_exception

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)

                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts - 1:
                        raise

                    delay = min(base_delay * (exponential_base ** attempt), max_delay)

                    if jitter:
                        delay *= (0.5 + random.random())

                    print(f"[Retry] Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                          f"Retrying in {delay:.2f}s...")

                    await asyncio.sleep(delay)

            raise last_exception

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator

# Convenience decorators for common scenarios
def retry_on_network_error(max_attempts: int = 3):
    """Retry on network-related errors"""
    import httpx
    return exponential_backoff_retry(
        max_attempts=max_attempts,
        base_delay=1.0,
        exceptions=(httpx.HTTPError, ConnectionError, TimeoutError)
    )

def retry_on_database_error(max_attempts: int = 3):
    """Retry on database-related errors"""
    try:
        import psycopg2
        exceptions = (psycopg2.OperationalError, psycopg2.InterfaceError)
    except ImportError:
        exceptions = (Exception,)

    return exponential_backoff_retry(
        max_attempts=max_attempts,
        base_delay=0.5,
        exceptions=exceptions
    )
