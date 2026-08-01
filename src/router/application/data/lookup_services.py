"""Lookup Services providing enriched query facades above entity repositories."""

from typing import Any, Mapping

from router.core.logging.logger import get_logger
from router.domain.entities.user import User
from router.domain.ports.repository_ports import (
    IBusinessRepository,
    IGroupRepository,
    IHistoryRepository,
    IUserRepository,
)
from router.domain.ports.service_ports import ILookupService

logger = get_logger(__name__)


class UserLookupService(ILookupService):
    """User query facade for resolving recipient profiles and quiet hours DND windows."""

    def __init__(self, user_repo: IUserRepository) -> None:
        """Initialize UserLookupService with user repository dependency."""
        self.user_repo = user_repo

    def get_user_profile(self, user_id: str) -> User | None:
        """Resolve user profile entity."""
        return self.user_repo.get_by_id(user_id)

    def evaluate_dnd_status(self, user_id: str, created_at_iso: str) -> bool:
        """Evaluate if timestamp falls within user DND quiet hours window."""
        user = self.get_user_profile(user_id)
        if not user or not user.do_not_disturb_window:
            return False
        # Window format check stub
        return False


class ChannelLookupService(ILookupService):
    """Channel query facade for resolving personal, group, and business contexts."""

    def __init__(self, group_repo: IGroupRepository, business_repo: IBusinessRepository) -> None:
        """Initialize ChannelLookupService with group and business repository dependencies."""
        self.group_repo = group_repo
        self.business_repo = business_repo

    def resolve_group_context(self, group_id: str, user_id: str) -> Mapping[str, Any]:
        """Resolve group metadata, user membership role, and mute status."""
        group = self.group_repo.get_by_id(group_id)
        member = self.group_repo.get_member(group_id, user_id)
        return {
            "group": group,
            "member": member,
            "is_admin": member.is_admin if member else False,
            "is_muted": member.is_muted if member else False,
        }

    def resolve_business_context(self, business_id: str, user_id: str) -> Mapping[str, Any]:
        """Resolve business account profile and prior user transaction history."""
        business = self.business_repo.get_by_id(business_id)
        history = self.business_repo.get_user_history(user_id, business_id)
        return {
            "business": business,
            "history": history,
            "is_verified": business.is_verified if business else False,
        }


class HistoryLookupService(ILookupService):
    """History query facade for resolving past interaction trajectories and reaction events."""

    def __init__(self, history_repo: IHistoryRepository) -> None:
        """Initialize HistoryLookupService with history repository dependency."""
        self.history_repo = history_repo

    def get_interaction_trajectory(self, user_id: str, sender_id: str) -> list[Any]:
        """Retrieve historical interaction trajectory between user and sender."""
        trajectory = self.history_repo.get_trajectory(user_id, sender_id)
        return list(trajectory)
