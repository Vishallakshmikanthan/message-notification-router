"""Unit test for logger configuration."""

from router.core.logging.logger import configure_logger, get_logger


def test_logger_configuration() -> None:
    """Verify logger setup and retrieval."""
    configure_logger(log_level="INFO", is_dev=True)
    logger = get_logger("test_module")
    assert logger is not None
