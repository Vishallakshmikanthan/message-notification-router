"""Multi-Level In-Memory ContextCache implementing L1, L2, and L3 caching topology."""

from typing import Any

from router.core.logging.logger import get_logger
from router.domain.entities.business import BusinessAccount, UserBusinessHistory
from router.domain.entities.group import Group, GroupMember
from router.domain.entities.user import User

logger = get_logger(__name__)


class ContextCache:
    """Multi-level in-memory cache for ultra-low latency context assembly."""

    def __init__(self, max_l1_entries: int = 10000) -> None:
        """Initialize L1 entity, L2 relational index, and L3 multimodal cache tiers."""
        self.max_l1_entries = max_l1_entries

        # L1 Hot Entity Cache: (user_id -> User), (business_id -> BusinessAccount), (group_id -> Group)
        self._l1_users: dict[str, User] = {}
        self._l1_businesses: dict[str, BusinessAccount] = {}
        self._l1_groups: dict[str, Group] = {}

        # L2 Relational Index Cache: ((group_id, user_id) -> GroupMember), ((user_id, business_id) -> UserBusinessHistory)
        self._l2_group_members: dict[tuple[str, str], GroupMember] = {}
        self._l2_user_business_history: dict[tuple[str, str], UserBusinessHistory] = {}

        # L3 Multimodal Cache: (sha256_hash -> ImageContext/VoiceContext)
        self._l3_multimodal: dict[str, Any] = {}

    # --- L1 Entity Tier ---
    def get_user(self, user_id: str) -> User | None:
        """Lookup user in L1 cache."""
        return self._l1_users.get(user_id)

    def put_user(self, user_id: str, user: User) -> None:
        """Store user in L1 cache."""
        if len(self._l1_users) >= self.max_l1_entries:
            self._l1_users.clear()
        self._l1_users[user_id] = user

    def get_business(self, business_id: str) -> BusinessAccount | None:
        """Lookup business account in L1 cache."""
        return self._l1_businesses.get(business_id)

    def put_business(self, business_id: str, business: BusinessAccount) -> None:
        """Store business account in L1 cache."""
        if len(self._l1_businesses) >= self.max_l1_entries:
            self._l1_businesses.clear()
        self._l1_businesses[business_id] = business

    def get_group(self, group_id: str) -> Group | None:
        """Lookup group in L1 cache."""
        return self._l1_groups.get(group_id)

    def put_group(self, group_id: str, group: Group) -> None:
        """Store group in L1 cache."""
        if len(self._l1_groups) >= self.max_l1_entries:
            self._l1_groups.clear()
        self._l1_groups[group_id] = group

    # --- L2 Relational Tier ---
    def get_group_member(self, group_id: str, user_id: str) -> GroupMember | None:
        """Lookup group member junction record in L2 index."""
        return self._l2_group_members.get((group_id, user_id))

    def put_group_member(self, group_id: str, user_id: str, member: GroupMember) -> None:
        """Store group member junction record in L2 index."""
        self._l2_group_members[(group_id, user_id)] = member

    def get_user_business_history(
        self, user_id: str, business_id: str
    ) -> UserBusinessHistory | None:
        """Lookup user-business history in L2 index."""
        return self._l2_user_business_history.get((user_id, business_id))

    def put_user_business_history(
        self, user_id: str, business_id: str, history: UserBusinessHistory
    ) -> None:
        """Store user-business history in L2 index."""
        self._l2_user_business_history[(user_id, business_id)] = history

    # --- L3 Multimodal Tier ---
    def get_multimodal(self, sha256_hash: str) -> Any | None:
        """Lookup multimodal artifact by content hash in L3 cache."""
        return self._l3_multimodal.get(sha256_hash)

    def put_multimodal(self, sha256_hash: str, artifact: Any) -> None:
        """Store pre-computed multimodal artifact in L3 cache."""
        self._l3_multimodal[sha256_hash] = artifact

    def clear(self) -> None:
        """Clear all cache tiers."""
        self._l1_users.clear()
        self._l1_businesses.clear()
        self._l1_groups.clear()
        self._l2_group_members.clear()
        self._l2_user_business_history.clear()
        self._l3_multimodal.clear()
