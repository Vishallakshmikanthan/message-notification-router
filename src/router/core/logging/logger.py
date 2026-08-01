"""Structured logging configurator using structlog with standard logging fallback adapter."""

import logging
import sys
from typing import Any

try:
    import structlog
    from structlog.types import Processor
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


class StandardLoggerAdapter:
    """Adapter wrapping standard logging.Logger to accept structured kwarg key-values."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _format(self, msg: str, kwargs: dict[str, Any]) -> str:
        if not kwargs:
            return msg
        kw_str = " ".join(f"{k}={v}" for k, v in kwargs.items())
        return f"{msg} | {kw_str}"

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(self._format(msg, kwargs), *args)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(self._format(msg, kwargs), *args)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(self._format(msg, kwargs), *args)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(self._format(msg, kwargs), *args)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.exception(self._format(msg, kwargs), *args)


def configure_logger(log_level: str = "INFO", is_dev: bool = False) -> None:
    """Configure globally formatted structured JSON or console logging."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    if HAS_STRUCTLOG:
        shared_processors: list[Processor] = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
        ]

        if is_dev:
            renderer: Processor = structlog.dev.ConsoleRenderer()
        else:
            renderer = structlog.processors.JSONRenderer()

        structlog.configure(
            processors=shared_processors + [renderer],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )


def get_logger(name: str) -> Any:
    """Get bound logger instance for a given module name."""
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return StandardLoggerAdapter(logging.getLogger(name))
