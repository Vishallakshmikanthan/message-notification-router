"""BusinessAccount and UserBusinessHistory Domain Entities."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class BusinessAccount:
    """Business sender account profile entity matching business_accounts.csv."""

    business_id: str
    business_name: str
    category: str
    official_domain: str
    is_verified: bool = False
    account_age_days: int = 0
    created_at: datetime = field(default_factory=_utc_now)


@dataclass(frozen=True)
class UserBusinessHistory:
    """User-Business interaction history entity matching user_business_history.csv."""

    user_id: str
    business_id: str
    has_prior_orders: bool = False
    opted_in_promotions: bool = True
    interaction_count_180d: int = 0
    last_interaction_at: datetime | None = None
