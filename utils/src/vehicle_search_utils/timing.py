from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from vehicle_search_utils.operation import OperationLogContext


def timed_run[ReturnValue](
    *,
    logger: logging.Logger,
    name: str | None = None,
) -> Callable[[Callable[..., ReturnValue]], Callable[..., ReturnValue]]:
    """Log the start and final status of a synchronous operation."""

    def decorator(inner_func: Callable[..., ReturnValue]) -> Callable[..., ReturnValue]:
        @wraps(inner_func)
        def wrapper(*args: Any, **kwargs: Any) -> ReturnValue:
            run = OperationLogContext(operation=name or inner_func.__name__)
            logger.info("timed_run_started", extra=run.started_extra(status="started"))

            try:
                result = inner_func(*args, **kwargs)
            except Exception as error:
                logger.exception(
                    "timed_run_failed",
                    extra=run.completed_extra(status="failed", error_type=type(error).__name__),
                )
                raise

            logger.info("timed_run_completed", extra=run.completed_extra(status="succeeded"))
            return result

        return wrapper

    return decorator
