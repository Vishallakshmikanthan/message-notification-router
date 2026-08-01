"""DataModelFactory for converting validated raw CSV rows into immutable domain entities."""

from datetime import date, datetime
from typing import Any, Mapping, Optional

from router.domain.entities.business import BusinessAccount, UserBusinessHistory
from router.domain.entities.group import Group, GroupMember
from router.domain.entities.history import (
    DailyNotificationSummary,
    HistoricalMessage,
    MessageEvent,
)
from router.domain.entities.media import ImageManifest, VoiceNoteManifest
from router.domain.entities.message import Message
from router.domain.entities.user import User
from router.infrastructure.memory.string_intern_pool import StringInternPool


class DataModelFactory:
    """Instantiates domain entities from CSV row dictionaries using string interning."""

    def __init__(self, string_pool: Optional[StringInternPool] = None) -> None:
        """Initialize DataModelFactory with optional StringInternPool."""
        self.string_pool = string_pool or StringInternPool()

    def _intern(self, val: Any) -> Any:
        """Intern string value if it is a string."""
        if isinstance(val, str):
            return self.string_pool.intern(val.strip())
        return val

    def _parse_bool(self, val: Any) -> bool:
        """Parse boolean from integer/string representation (0/1 or true/false)."""
        if val is None:
            return False
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        return s in ("1", "true", "yes", "t")

    def _parse_datetime(self, val: Any) -> datetime:
        """Parse ISO 8601 or YYYY-MM-DD HH:MM:SS datetime string."""
        if isinstance(val, datetime):
            return val
        s = str(val).strip()
        if not s:
            return datetime.now()
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            try:
                return datetime.strptime(s, "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return datetime.now()

    def _parse_date(self, val: Any) -> date:
        """Parse YYYY-MM-DD date string."""
        if isinstance(val, date):
            return val
        s = str(val).strip()
        if not s:
            return date.today()
        try:
            return date.fromisoformat(s)
        except ValueError:
            return date.today()

    def create_user(self, row: Mapping[str, Any]) -> User:
        """Instantiate User entity from users.csv row."""
        return User(
            user_id=self._intern(row["user_id"]),
            name=str(row.get("name", row.get("user_name", ""))),
            user_name=str(row.get("user_name", row.get("name", ""))),
            phone_number=str(row.get("phone_number", "")),
            user_type=self._intern(row.get("user_type", "INDIVIDUAL")),
            registration_date=self._parse_datetime(row.get("registration_date", "")),
            preferred_language=self._intern(row.get("preferred_language", "en")),
            timezone=self._intern(row.get("timezone", "UTC")),
            is_verified=self._parse_bool(row.get("is_verified", False)),
            do_not_disturb_window=row.get("do_not_disturb_window"),
            messages_opened_30d=int(row.get("messages_opened_30d", 0)),
            messages_replied_30d=int(row.get("messages_replied_30d", 0)),
            notifications_dismissed_30d=int(row.get("notifications_dismissed_30d", 0)),
            messages_reported_30d=int(row.get("messages_reported_30d", 0)),
        )

    def create_group(self, row: Mapping[str, Any]) -> Group:
        """Instantiate Group entity from groups.csv row."""
        return Group(
            group_id=self._intern(row["group_id"]),
            group_name=str(row.get("group_name", "")),
            group_type=self._intern(row.get("group_type", "COMMUNITY")),
            created_at=self._parse_datetime(row.get("created_at", "")),
            member_count=int(row.get("member_count", 0)),
            admin_count=int(row.get("admin_count", 0)),
            is_announcement_only=self._parse_bool(row.get("is_announcement_only", False)),
        )

    def create_group_member(self, row: Mapping[str, Any]) -> GroupMember:
        """Instantiate GroupMember entity from group_members.csv row."""
        return GroupMember(
            group_id=self._intern(row["group_id"]),
            user_id=self._intern(row["user_id"]),
            role=self._intern(row.get("role", "member")),
            joined_at=self._parse_datetime(row.get("joined_at", "")),
            messages_sent_30d=int(row.get("messages_sent_30d", 0)),
            messages_read_30d=int(row.get("messages_read_30d", 0)),
            replies_sent_30d=int(row.get("replies_sent_30d", 0)),
            notifications_dismissed_30d=int(row.get("notifications_dismissed_30d", 0)),
            is_muted=self._parse_bool(row.get("group_muted_by_user", row.get("is_muted", False))),
        )

    def create_business_account(self, row: Mapping[str, Any]) -> BusinessAccount:
        """Instantiate BusinessAccount entity from business_accounts.csv row."""
        display = str(row.get("display_name", ""))
        brand = str(row.get("brand_name", ""))
        verified = self._parse_bool(row.get("verified", False))

        return BusinessAccount(
            business_id=self._intern(row["business_id"]),
            display_name=display,
            brand_name=brand,
            business_name=brand or display,
            category=self._intern(row.get("category", "SERVICES")),
            verified=verified,
            is_verified=verified,
            official_domain=self._intern(row.get("official_domain", "")),
            domain_used_by_sender=self._intern(row.get("domain_used_by_sender", "")),
            account_age_days=int(row.get("account_age_days", 0)),
            messages_sent_30d=int(row.get("messages_sent_30d", 0)),
            user_reports_30d=int(row.get("user_reports_30d", 0)),
            domain_used_by_sender_age_days=int(row.get("domain_used_by_sender_age_days", 0)),
        )

    def create_user_business_history(self, row: Mapping[str, Any]) -> UserBusinessHistory:
        """Instantiate UserBusinessHistory entity from user_business_history.csv row."""
        opted_out = row.get("promotions_opted_out_at")
        last_act = row.get("last_activity_at")
        last_rep = row.get("last_reply_at")

        return UserBusinessHistory(
            user_id=self._intern(row["user_id"]),
            business_id=self._intern(row["business_id"]),
            why_user_knows_account=str(row.get("why_user_knows_account", "")),
            allows_promotions=self._parse_bool(row.get("allows_promotions", True)),
            opted_in_promotions=self._parse_bool(row.get("allows_promotions", True)),
            promotions_opted_out_at=self._parse_datetime(opted_out) if opted_out else None,
            activity_count_180d=int(row.get("activity_count_180d", 0)),
            messages_opened_30d=int(row.get("messages_opened_30d", 0)),
            messages_dismissed_30d=int(row.get("notifications_dismissed_30d", row.get("messages_dismissed_30d", 0))),
            messages_replied_30d=int(row.get("messages_replied_30d", 0)),
            last_activity_at=self._parse_datetime(last_act) if last_act else None,
            last_reply_at=self._parse_datetime(last_rep) if last_rep else None,
        )

    def create_image_manifest(self, row: Mapping[str, Any]) -> ImageManifest:
        """Instantiate ImageManifest entity from images.csv row."""
        img_id = self._intern(row["image_id"])
        return ImageManifest(
            media_id=img_id,
            image_id=img_id,
            file_path=str(row.get("file_path", "")),
            file_size_bytes=int(row.get("file_size_bytes", 0)),
            width_px=int(row.get("width_px", 0)),
            height_px=int(row.get("height_px", 0)),
            mime_type=self._intern(row.get("mime_type", "image/jpeg")),
        )

    def create_voice_note_manifest(self, row: Mapping[str, Any]) -> VoiceNoteManifest:
        """Instantiate VoiceNoteManifest entity from voice_notes.csv row."""
        vn_id = self._intern(row["voice_note_id"])
        return VoiceNoteManifest(
            media_id=vn_id,
            voice_note_id=vn_id,
            file_path=str(row.get("file_path", "")),
            duration_seconds=float(row.get("duration_seconds", 0.0)),
            audio_codec=self._intern(row.get("audio_codec", "opus")),
            file_size_bytes=int(row.get("file_size_bytes", 0)),
        )

    def create_historical_message(self, row: Mapping[str, Any]) -> HistoricalMessage:
        """Instantiate HistoricalMessage entity from message_history.csv row."""
        return HistoricalMessage(
            message_id=self._intern(row["message_id"]),
            user_id=self._intern(row["user_id"]),
            sender_id=self._intern(row.get("sender_id", row.get("sender_user_id", ""))),
            conversation_type=self._intern(row.get("conversation_type", "personal")),
            message_text=str(row.get("message_text", "")),
            created_at=self._parse_datetime(row.get("created_at", "")),
            business_id=self._intern(row.get("business_id")) if row.get("business_id") else None,
            group_id=self._intern(row.get("group_id")) if row.get("group_id") else None,
        )

    def create_message_event(self, row: Mapping[str, Any]) -> MessageEvent:
        """Instantiate MessageEvent entity from message_events.csv row."""
        u_id = self._intern(row.get("user_id", ""))
        m_id = self._intern(row.get("message_id", ""))
        evt_id = self._intern(row.get("event_id", f"evt_{u_id}_{m_id}"))
        evt_type = "OPENED" if self._parse_bool(row.get("message_opened")) else ("REPLIED" if self._parse_bool(row.get("message_replied")) else "DELIVERED")

        return MessageEvent(
            event_id=evt_id,
            message_id=m_id,
            user_id=u_id,
            event_type=evt_type,
            event_timestamp=datetime.now(),
            details=str(row),
        )

    def create_daily_notification_summary(self, row: Mapping[str, Any]) -> DailyNotificationSummary:
        """Instantiate DailyNotificationSummary entity from daily_notification_summary.csv row."""
        u_id = self._intern(row.get("user_id", ""))
        d_val = row.get("date", row.get("summary_date", ""))
        sum_id = self._intern(row.get("summary_id", f"sum_{u_id}_{d_val}"))

        return DailyNotificationSummary(
            summary_id=sum_id,
            user_id=u_id,
            summary_date=self._parse_date(d_val),
            messages_received=int(row.get("notifications_sent", row.get("messages_received", 0))),
            notifications_opened=int(row.get("notifications_opened", 0)),
            notifications_dismissed=int(row.get("notifications_dismissed", 0)),
            avg_response_time_seconds=float(row.get("avg_response_time_seconds", 0.0)),
        )

    def create_message(self, row: Mapping[str, Any]) -> Message:
        """Instantiate Message entity from messages.csv row."""
        m_id = row.get("media_id")
        m_type = row.get("media_type")
        g_id = row.get("group_id")
        b_id = row.get("business_id")
        s_id = row.get("sender_user_id")

        return Message(
            message_id=self._intern(row["message_id"]),
            user_id=self._intern(row["user_id"]),
            sender_user_id=self._intern(s_id) if s_id and str(s_id).upper() != "NONE" else None,
            conversation_type=self._intern(row.get("conversation_type", "personal")),
            group_id=self._intern(g_id) if g_id and str(g_id).upper() != "NONE" else None,
            business_id=self._intern(b_id) if b_id and str(b_id).upper() != "NONE" else None,
            message_text=str(row.get("message_text", "")),
            media_type=self._intern(m_type) if m_type and str(m_type).upper() != "NONE" else None,
            media_id=self._intern(m_id) if m_id and str(m_id).upper() != "NONE" else None,
            created_at=self._parse_datetime(row.get("created_at", "")),
            forwarded_count=int(row.get("forwarded_count", 0)),
        )
