"""Lookup Services providing enriched query facades above entity repositories."""

from datetime import datetime, time
from typing import Any

from router.core.logging.logger import get_logger
from router.domain.entities.user import User
from router.domain.ports.repository_ports import (
    IBusinessRepository,
    IEventRepository,
    IGroupRepository,
    IHistoryRepository,
    INotificationSummaryRepository,
    IUserRepository,
)
from router.domain.ports.service_ports import ILookupService

logger = get_logger(__name__)


class UserLookupService(ILookupService):
    """User query facade for resolving recipient profiles, activity metrics, and quiet hours DND windows."""

    def __init__(
        self,
        user_repo: IUserRepository,
        summary_repo: INotificationSummaryRepository | None = None,
    ) -> None:
        """Initialize UserLookupService with user repository dependencies."""
        self.user_repo = user_repo
        self.summary_repo = summary_repo

    def get_user_profile(self, user_id: str) -> User | None:
        """Resolve user profile entity."""
        return self.user_repo.get_by_id(user_id)

    def evaluate_dnd_status(self, user_id: str, current_dt: datetime | None = None) -> dict[str, Any]:
        """Evaluate if timestamp falls within user do_not_disturb_window, handling midnight wraps."""
        user = self.get_user_profile(user_id)
        if not user or not user.do_not_disturb_window:
            return {"is_dnd_active": False, "window_start": None, "window_end": None}

        window_str = str(user.do_not_disturb_window).strip()
        parts = window_str.split("-")
        if len(parts) != 2:
            return {"is_dnd_active": False, "window_start": None, "window_end": None}

        dt = current_dt or datetime.utcnow()
        current_time = dt.time()

        try:
            sh, sm = map(int, parts[0].split(":"))
            eh, em = map(int, parts[1].split(":"))
            start_t = time(sh, sm)
            end_t = time(eh, em)

            if start_t <= end_t:
                is_active = start_t <= current_time <= end_t
            else:
                # Overnight wrap (e.g. 22:00 - 07:00)
                is_active = current_time >= start_t or current_time <= end_t

            return {
                "is_dnd_active": is_active,
                "window_start": start_t,
                "window_end": end_t,
            }
        except Exception:
            return {"is_dnd_active": False, "window_start": None, "window_end": None}

    def get_user_activity_metrics(self, user_id: str) -> dict[str, float]:
        """Calculate global 30-day engagement ratios."""
        user = self.get_user_profile(user_id)
        if not user:
            return {"open_rate": 0.0, "reply_rate": 0.0, "report_ratio": 0.0}

        opened = float(user.messages_opened_30d)
        dismissed = float(user.notifications_dismissed_30d)
        replied = float(user.messages_replied_30d)
        reported = float(user.messages_reported_30d)

        total_received = opened + dismissed
        open_rate = (opened / total_received) if total_received > 0 else 0.0
        reply_rate = (replied / opened) if opened > 0 else 0.0
        report_ratio = (reported / opened) if opened > 0 else 0.0

        return {
            "open_rate": round(open_rate, 4),
            "reply_rate": round(reply_rate, 4),
            "report_ratio": round(report_ratio, 4),
        }


class ChannelLookupService(ILookupService):
    """Channel query facade for resolving Personal, Group, and Business context Modalites."""

    def __init__(
        self,
        group_repo: IGroupRepository,
        business_repo: IBusinessRepository,
        user_repo: IUserRepository | None = None,
        history_repo: IHistoryRepository | None = None,
    ) -> None:
        """Initialize ChannelLookupService with group and business repository dependencies."""
        self.group_repo = group_repo
        self.business_repo = business_repo
        self.user_repo = user_repo
        self.history_repo = history_repo

    def resolve_personal_channel(self, user_id: str, sender_user_id: str) -> dict[str, Any]:
        """Fetch sender profile and compute mutual groups intersection count."""
        sender = self.user_repo.get_by_id(sender_user_id) if self.user_repo else None

        # Compute mutual group count
        mutual_count = 0
        if self.group_repo and hasattr(self.group_repo, "_members_index"):
            user_groups = {g_id for (g_id, u_id) in self.group_repo._members_index.keys() if u_id == user_id}
            sender_groups = {g_id for (g_id, u_id) in self.group_repo._members_index.keys() if u_id == sender_user_id}
            mutual_count = len(user_groups.intersection(sender_groups))

        return {
            "sender": sender,
            "mutual_groups_count": mutual_count,
        }

    def resolve_group_context(self, group_id: str, user_id: str) -> dict[str, Any]:
        """Resolve group metadata, user membership role, and mute status in O(1) time."""
        group = self.group_repo.get_by_id(group_id)
        member = self.group_repo.get_member(group_id, user_id)
        is_admin = self.group_repo.is_admin(group_id, user_id)

        return {
            "group": group,
            "member": member,
            "is_admin": is_admin,
            "is_muted": member.is_muted if member else False,
            "messages_sent_30d": member.messages_sent_30d if member else 0,
            "messages_read_30d": member.messages_read_30d if member else 0,
        }

    def resolve_business_context(self, user_id: str, business_id: str) -> dict[str, Any]:
        """Resolve business account profile, history, domain mismatch flag, and promotional consent."""
        business = self.business_repo.get_by_id(business_id)
        history = self.business_repo.get_user_history(user_id, business_id)

        domain_mismatch = False
        if business and history:
            official = business.official_domain.strip().lower()
            sender_domain = history.domain_used_by_sender.strip().lower()
            if official and sender_domain and official != sender_domain:
                domain_mismatch = True

        allows_promotions = history.allows_promotions if history else True

        return {
            "business": business,
            "history": history,
            "domain_mismatch_flag": domain_mismatch,
            "allows_promotions": allows_promotions,
            "is_verified": business.is_verified if business else False,
        }


class HistoryLookupService(ILookupService):
    """History query facade for resolving past interaction trajectories and reaction events."""

    def __init__(
        self,
        history_repo: IHistoryRepository,
        event_repo: IEventRepository | None = None,
        summary_repo: INotificationSummaryRepository | None = None,
    ) -> None:
        """Initialize HistoryLookupService with history repository dependencies."""
        self.history_repo = history_repo
        self.event_repo = event_repo
        self.summary_repo = summary_repo

    def get_interaction_trajectory(self, user_id: str, sender_or_business_id: str) -> dict[str, Any]:
        """Retrieve historical interaction trajectory between user and sender/business."""
        messages = self.history_repo.get_trajectory(user_id, sender_or_business_id)
        total_messages = len(messages)

        last_interaction_ts: datetime | None = None
        days_since_last: float = 999.0

        if total_messages > 0:
            last_msg = messages[-1]
            last_interaction_ts = last_msg.created_at
            now = datetime.utcnow()
            days_since_last = max(0.0, (now - last_interaction_ts).total_seconds() / 86400.0)

        return {
            "total_messages_exchanged": total_messages,
            "messages": list(messages),
            "last_interaction_timestamp": last_interaction_ts,
            "days_since_last_interaction": round(days_since_last, 2),
        }

    def get_daily_notification_baseline(self, user_id: str, date_str: str) -> dict[str, Any]:
        """Retrieve daily notification baseline for user."""
        summary = self.summary_repo.get_summary(user_id, date_str) if self.summary_repo else None

        return {
            "summary": summary,
            "messages_received": summary.messages_received if summary else 0,
            "notifications_opened": summary.notifications_opened if summary else 0,
            "notifications_dismissed": summary.notifications_dismissed if summary else 0,
            "avg_response_time_seconds": summary.avg_response_time_seconds if summary else 0.0,
        }
