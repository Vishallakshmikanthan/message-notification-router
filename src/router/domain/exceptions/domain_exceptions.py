"""Domain-specific Exceptions for Business Invariant & Validation Violations."""

from typing import Any

from router.core.constants.error_codes import ErrorCode
from router.core.exceptions.base_exceptions import RouterError


class DomainError(RouterError):
    """Base exception for all domain model violations."""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.ERR_INVALID_PAYLOAD,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, error_code=error_code, status_code=status_code, details=details)


class EntityNotFoundError(DomainError):
    """Exception raised when requested entity does not exist in domain storage."""

    def __init__(self, entity_name: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_name} with identifier '{entity_id}' was not found.",
            error_code=ErrorCode.ERR_RESOURCE_NOT_FOUND,
            status_code=404,
            details={"entity_name": entity_name, "entity_id": entity_id},
        )


class DuplicateEntityError(DomainError):
    """Exception raised when trying to store duplicate entity key."""

    def __init__(self, entity_name: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_name} with identifier '{entity_id}' already exists.",
            error_code=ErrorCode.ERR_INVALID_PAYLOAD,
            status_code=409,
            details={"entity_name": entity_name, "entity_id": entity_id},
        )


class ValidationFailedError(DomainError):
    """Exception raised when domain schema or referential constraint validation fails."""

    pass


class InvalidPayloadException(ValidationFailedError):
    """Exception raised when raw message payload is invalid or corrupted."""

    pass

