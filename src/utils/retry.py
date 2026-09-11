import asyncio
import logging
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


async def retry_async(
        operation: Callable[[], Awaitable[T]],
        *,
        description: str,
        logger: logging.Logger,
        attempts: int,
        base_delay: float,
        max_delay: float = 30.0,
        should_retry: Callable[[Exception], bool] = lambda _: True,
) -> T:
    """Run `operation`, retrying failures with linear backoff capped at `max_delay`.

    The last exception is re-raised once attempts are exhausted or `should_retry` rejects it.
    """
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as e:
            if not should_retry(e):
                raise
            logger.error(f"{description} failed (attempt {attempt}/{attempts}): {e}")
            if attempt >= attempts:
                raise
            await asyncio.sleep(min(base_delay * attempt, max_delay))
    raise RuntimeError("unreachable")
