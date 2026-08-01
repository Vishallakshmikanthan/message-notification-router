"""Base Exception Hierarchy for system-wide exception handling."""

from typing import Any

from router.core.constants.error_codes import ErrorCode


class RouterError(Exception):
    """Root system exception for all application custom exceptions."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.ERR_INTERNAL_SERVER_ERROR,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class ApplicationError(RouterError):
    """Base exception for application-level workflow errors."""

    pass


class InfrastructureError(RouterError):
    """Base exception for external technical failure conditions."""

    pass
