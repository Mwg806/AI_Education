"""Bounded async retry support used by tool and model harnesses."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from ai_education.core.errors import AIEducationError

T = TypeVar("T")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 0.05,
) -> T:
    """Retry only explicitly retryable failures, never more than three times."""

    bounded_attempts = min(max(attempts, 1), 3)
    for attempt in range(1, bounded_attempts + 1):
        try:
            return await operation()
        except AIEducationError as exc:
            if not exc.retryable or attempt == bounded_attempts:
                raise
            await asyncio.sleep(base_delay_seconds * (2 ** (attempt - 1)))
    raise RuntimeError("unreachable")

