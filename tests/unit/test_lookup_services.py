"""Unit tests for UserLookupService, ChannelLookupService, and HistoryLookupService."""

from datetime import datetime

from router.application.data.lookup_services import (
    ChannelLookupService,
    UserLookupService,
)
from router.domain.entities.business import BusinessAccount, UserBusinessHistory
from router.domain.entities.user import User
from router.infrastructure.repositories.business_repository import BusinessRepository
from router.infrastructure.repositories.group_repository import GroupRepository
from router.infrastructure.repositories.user_repository import UserRepository


def test_user_lookup_service_dnd_evaluation() -> None:
    """Verify DND quiet hours window evaluation including overnight wraps."""
    repo = UserRepository()
    user = User(user_id="u_001", name="Alice", do_not_disturb_window="22:00-07:00")
    repo.add(user.user_id, user)

    service = UserLookupService(repo)

    # 23:30 is within 22:00-07:00
    dt_night = datetime(2026, 8, 1, 23, 30, 0)
    res1 = service.evaluate_dnd_status("u_001", dt_night)
    assert res1["is_dnd_active"] is True

    # 12:00 is outside 22:00-07:00
    dt_noon = datetime(2026, 8, 1, 12, 0, 0)
    res2 = service.evaluate_dnd_status("u_001", dt_noon)
    assert res2["is_dnd_active"] is False


def test_channel_lookup_service_domain_mismatch() -> None:
    """Verify domain mismatch detection logic in ChannelLookupService."""
    group_repo = GroupRepository()
    biz_repo = BusinessRepository()

    biz = BusinessAccount(
        business_id="business_001",
        business_name="BankCorp",
        official_domain="bankcorp.com",
    )
    hist = UserBusinessHistory(
        user_id="u_001",
        business_id="business_001",
        domain_used_by_sender="fakebankcorp.net",
    )
    biz_repo.add(biz.business_id, biz)
    biz_repo.add_user_history(hist)

    service = ChannelLookupService(group_repo, biz_repo)
    ctx = service.resolve_business_context("u_001", "business_001")

    assert ctx["business"] == biz
    assert ctx["domain_mismatch_flag"] is True
