"""GroupRepository implementation matching groups.csv and group_members.csv."""

from router.domain.entities.group import Group, GroupMember
from router.domain.ports.repository_ports import IGroupRepository
from router.infrastructure.repositories.base_repository import BaseRepository


class GroupRepository(BaseRepository[Group, str], IGroupRepository):
    """Manages WhatsApp group metadata and member junction indexes."""

    def __init__(self) -> None:
        """Initialize GroupRepository junction indexes."""
        super().__init__()
        self._members_index: dict[tuple[str, str], GroupMember] = {}

    def add_member(self, member: GroupMember) -> None:
        """Add group member junction entity."""
        self._members_index[(member.group_id, member.user_id)] = member

    def get_member(self, group_id: str, user_id: str) -> GroupMember | None:
        """Get group member junction entity by composite key."""
        return self._members_index.get((group_id, user_id))

    def is_admin(self, group_id: str, user_id: str) -> bool:
        """Verify if user is group administrator."""
        member = self.get_member(group_id, user_id)
        return member.is_admin if member else False

    def clear(self) -> None:
        """Clear store and member indexes."""
        super().clear()
        self._members_index.clear()
