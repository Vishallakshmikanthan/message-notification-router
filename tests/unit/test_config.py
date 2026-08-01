"""Unit tests for system configuration settings."""

from router.core.config.settings import get_settings


def test_get_settings_defaults() -> None:
    """Verify default system settings loaded via Pydantic."""
    settings = get_settings()
    assert settings.app_name == "whatsapp-notification-router"
    assert settings.log_level in ["INFO", "DEBUG", "WARN", "ERROR"]
    assert settings.db.port == 5432
    assert "postgresql+asyncpg" in settings.db.async_url
