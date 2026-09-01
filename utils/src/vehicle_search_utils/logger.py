import logging
import logging.handlers
from pathlib import Path

from rich.logging import RichHandler

from vehicle_search_utils.settings import settings

LOG_RECORD_BUILTIN_KEYS = set(
    logging.LogRecord(
        name="",
        level=0,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__.keys()
)
CONTEXT_EXCLUDED_KEYS = LOG_RECORD_BUILTIN_KEYS | {"message", "asctime"}
TIMING_CONTEXT_KEYS = (
    "started_at_utc",
    "ended_at_utc",
    "duration_ms",
    "duration_human",
)
TIMING_CONTEXT_KEY_SET = set(TIMING_CONTEXT_KEYS)


class ContextAwareFormatter(logging.Formatter):
    """
    Append operation and timing `extra` fields as separate context groups.
    """

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)

        context_keys = {key for key in record.__dict__ if key not in CONTEXT_EXCLUDED_KEYS}
        operation_parts = [f"{key}={record.__dict__[key]}" for key in sorted(context_keys - TIMING_CONTEXT_KEY_SET)]
        timing_parts = [f"{key}={record.__dict__[key]}" for key in TIMING_CONTEXT_KEYS if key in context_keys]

        context_groups = [" ".join(parts) for parts in (operation_parts, timing_parts) if parts]
        if not context_groups:
            return base

        return " | ".join((base, *context_groups))


def _get_log_level(level_name: str) -> int:
    return getattr(logging, level_name.upper(), logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger singleton for `name`.

    The logger includes optional console/file handlers based on settings.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = _get_log_level(settings.logging.level)

    logger.setLevel(log_level)
    logger.propagate = False

    if settings.logging.console_enabled:
        console_handler = RichHandler(rich_tracebacks=True)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(ContextAwareFormatter("%(name)s - %(message)s"))
        logger.addHandler(console_handler)

    if settings.logging.file_enabled:
        log_filename = settings.logging.file_name or f"{settings.project_name}.log"
        log_path = Path(settings.log_dir) / log_filename

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=settings.logging.max_bytes,
            backupCount=settings.logging.backup_count,
            delay=True,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(ContextAwareFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)

    return logger
