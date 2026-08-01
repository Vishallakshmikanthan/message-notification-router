"""Domain-level custom exception definitions."""

from router.core.exceptions.base_exceptions import RouterError


class DomainError(RouterError):
    """Base class for all enterprise domain exception conditions."""

    pass


class InvalidMessageIdError(DomainError):
    """Raised when a message identifier violates structural or format rules."""

    pass


class InvalidMediaFormatError(DomainError):
    """Raised when an incoming media payload has an unsupported or corrupted format."""

    pass


class PreferenceValidationError(DomainError):
    """Raised when user preference settings contain invalid configurations."""

    pass
