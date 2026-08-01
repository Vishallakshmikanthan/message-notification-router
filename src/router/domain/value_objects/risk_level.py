"""Risk Level Value Object representing message security and safety severity."""

from enum import StrEnum


class RiskLevel(StrEnum):
    """Categorical risk levels assigned by safety & risk engines."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
