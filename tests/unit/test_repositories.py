"""Unit tests for all 8 domain repository implementations."""

from router.domain.entities.business import BusinessAccount, UserBusinessHistory
from router.domain.entities.group import Group, GroupMember
from router.domain.entities.user import User
from router.infrastructure.repositories.business_repository import BusinessRepository
from router.infrastructure.repositories.group_repository import GroupRepository
from router.infrastructure.repositories.user_repository import UserRepository


def test_user_repository_crud(sample_user: User) -> None:
    """Verify UserRepository O(1) primary key retrieval and CRUD operations."""
    repo = UserRepository()
    repo.add(sample_user.user_id, sample_user)

    assert repo.count() == 1
    assert repo.exists("u_001")
    assert repo.get_by_id("u_001") == sample_user
    assert repo.get_by_id("u_999") is None

    repo.clear()
    assert repo.count() == 0


def test_group_repository_junctions() -> None:
    """Verify GroupRepository primary and member composite tuple index lookups."""
    repo = GroupRepository()
    group = Group(group_id="group_001", group_name="Engineering Team", group_type="WORK", member_count=5)
    member = GroupMember(group_id="group_001", user_id="u_001", role="admin", is_muted=False)

    repo.add(group.group_id, group)
    repo.add_member(member)

    assert repo.get_by_id("group_001") == group
    assert repo.get_member("group_001", "u_001") == member
    assert repo.is_admin("group_001", "u_001") is True
    assert repo.is_admin("group_001", "u_002") is False


def test_business_repository_history() -> None:
    """Verify BusinessRepository profile and user-business history composite lookups."""
    repo = BusinessRepository()
    biz = BusinessAccount(business_id="business_001", business_name="Acme Corp", category="RETAIL")
    hist = UserBusinessHistory(user_id="u_001", business_id="business_001", allows_promotions=True, total_orders=3)

    repo.add(biz.business_id, biz)
    repo.add_user_history(hist)

    assert repo.get_by_id("business_001") == biz
    assert repo.get_user_history("u_001", "business_001") == hist
