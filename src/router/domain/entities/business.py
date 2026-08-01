"""BusinessAccount and UserBusinessHistory Domain Entities matching business_accounts.csv and user_business_history.csv."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class BusinessAccount:
    """Business sender account profile entity matching business_accounts.csv."""

    business_id: str
    display_name: str = ""
    brand_name: str = ""
    business_name: str = ""
    category: str = "SERVICES"
    verified: bool = False
    is_verified: bool = False
    verification_status: str = "UNVERIFIED"
    official_domain: str = ""
    domain_used_by_sender: str = ""
    account_age_days: int = 0
    messages_sent_30d: int = 0
    user_reports_30d: int = 0
    domain_used_by_sender_age_days: int = 0
    support_email: str = ""
    catalog_enabled: bool = False
    expected_sla_minutes: int = 60
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        if not self.business_name and (self.display_name or self.brand_name):
            object.__setattr__(self, "business_name", self.display_name or self.brand_name)
        if self.verified and not self.is_verified:
            object.__setattr__(self, "is_verified", True)


@dataclass(frozen=True)
class UserBusinessHistory:
    """User-Business interaction history entity matching user_business_history.csv."""

    user_id: str
    business_id: str
    why_user_knows_account: str = ""
    allows_promotions: bool = True
    opted_in_promotions: bool = True
    promotions_opted_out_at: Optional[datetime] = None
    activity_count_180d: int = 0
    interaction_count_180d: int = 0
    messages_opened_30d: int = 0
    messages_dismissed_30d: int = 0
    messages_replied_30d: int = 0
    domain_used_by_sender: str = ""
    domain_used_by_sender_age_days: int = 0
    total_orders: int = 0
    total_spend: float = 0.0
    last_order_timestamp: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    last_reply_at: Optional[datetime] = None
