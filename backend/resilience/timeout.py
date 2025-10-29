# backend/resilience/timeout.py
"""
Timeout Strategy
Google SRE: Always set explicit timeouts to prevent resource exhaustion
"""
import signal
import asyncio
from typing import Callable, Any
from functools import wraps

class TimeoutError(Exception):
    """Raised when function execution exceeds timeout"""
    pass

def timeout(seconds: float):
    """
    Timeout decorator for synchronous functions

    Google SRE Best Practice:
    - Always set explicit timeouts
    - Fail fast on timeout
    - Release resources immediately

    Args:
        seconds: Timeout in seconds
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            def timeout_handler(signum, frame):
                raise TimeoutError(f"{func.__name__} exceeded {seconds}s timeout")

            # Set alarm signal
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(seconds))

            try:
                result = func(*args, **kwargs)
            finally:
                # Reset alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            return result

        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"{func.__name__} exceeded {seconds}s timeout")

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator

# Convenience decorators for common scenarios
def api_timeout(seconds: float = 30.0):
    """Standard timeout for API calls"""
    return timeout(seconds)

def database_timeout(seconds: float = 10.0):
    """Standard timeout for database queries"""
    return timeout(seconds)

def computation_timeout(seconds: float = 120.0):
    """Standard timeout for heavy computations"""
    return timeout(seconds)
