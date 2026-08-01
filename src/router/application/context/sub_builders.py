"""Sub-Context Builders for individual domain context extraction and enrichment."""

from datetime import datetime, timezone
import math
from typing import List, Optional

from router.core.logging.logger import get_logger
from router.domain.entities.raw_message import RawMessagePayload
from router.domain.entities.sub_contexts import (
    DEFAULT_BEHAVIOUR_CONTEXT,
    DEFAULT_BUSINESS_CONTEXT,
    DEFAULT_CONVERSATION_CONTEXT,
    DEFAULT_GROUP_CONTEXT,
    DEFAULT_HISTORY_CONTEXT,
    DEFAULT_MEDIA_CONTEXT,
    DEFAULT_NOTIFICATION_CONTEXT,
    DEFAULT_RELATIONSHIP_CONTEXT,
    DEFAULT_USER_CONTEXT,
    BehaviourContext,
    BusinessContext,
    ConversationContext,
    GroupContext,
    HistoryContext,
    MediaContext,
    NotificationContext,
    RelationshipContext,
    UserContext,
)
from router.infrastructure.cache.context_cache import ContextCache
from router.infrastructure.repositories.context_repository_registry import ContextRepositoryRegistry

logger = get_logger(__name__)


class UserContextBuilder:
    """Sub-context builder for UserContext models (Sender & Receiver)."""

    def build(
        self,
        phone_or_id: str,
        registry: ContextRepositoryRegistry,
        cache: Optional[ContextCache] = None,
        now_ts_ms: Optional[int] = None,
    ) -> UserContext:
        """Construct UserContext instance from repository or cache, falling back to default."""
        if not phone_or_id or phone_or_id in ("NONE", "UNKNOWN", "UNKNOWN_USER", ""):
            return DEFAULT_USER_CONTEXT


        # Check L1 cache
        if cache:
            cached = cache.get_user(phone_or_id)
            if cached:
                now_ms = now_ts_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
                reg_ts = getattr(cached, "created_at_epoch_ms", 0) or 0
                age_days = max(0, int((now_ms - reg_ts) / (1000 * 86400))) if reg_ts > 0 else 0
                return UserContext(
                    user_id=cached.user_id,
                    display_name=cached.display_name or "User",
                    phone_number=cached.phone_number or phone_or_id,
                    user_type="INDIVIDUAL",
                    registration_timestamp=reg_ts,
                    account_age_days=age_days,
                    preferred_language=cached.preferred_language or "en",
                    timezone=cached.timezone or "UTC",
                    is_verified=cached.is_verified,
                    is_registered_user=True,
                )

        # Check Repository
        if registry.users_repo:
            user = registry.users_repo.get_by_id(phone_or_id)
            if user:
                if cache:
                    cache.put_user(phone_or_id, user)
                now_ms = now_ts_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
                reg_ts = getattr(user, "created_at_epoch_ms", 0) or 0
                age_days = max(0, int((now_ms - reg_ts) / (1000 * 86400))) if reg_ts > 0 else 0
                return UserContext(
                    user_id=user.user_id,
                    display_name=user.display_name or "User",
                    phone_number=user.phone_number or phone_or_id,
                    user_type="INDIVIDUAL",
                    registration_timestamp=reg_ts,
                    account_age_days=age_days,
                    preferred_language=user.preferred_language or "en",
                    timezone=user.timezone or "UTC",
                    is_verified=user.is_verified,
                    is_registered_user=True,
                )

        # Fallback profile for unregistered user
        return UserContext(
            user_id=phone_or_id,
            display_name=f"Contact ({phone_or_id})",
            phone_number=phone_or_id,
            user_type="INDIVIDUAL",
            registration_timestamp=0,
            account_age_days=0,
            preferred_language="en",
            timezone="UTC",
            is_verified=False,
            is_registered_user=False,
        )


class GroupContextBuilder:
    """Sub-context builder for GroupContext models."""

    def build(
        self,
        group_id: str,
        sender_phone_or_id: str,
        registry: ContextRepositoryRegistry,
        cache: Optional[ContextCache] = None,
    ) -> GroupContext:
        """Construct GroupContext instance for group chats, falling back for DMs."""
        if not group_id or group_id in ("NONE", "DM", ""):
            return DEFAULT_GROUP_CONTEXT

        # Check Cache L1 & L2
        group = cache.get_group(group_id) if cache else None
        if not group and registry.groups_repo:
            group = registry.groups_repo.get_by_id(group_id)
            if group and cache:
                cache.put_group(group_id, group)

        if not group:
            return DEFAULT_GROUP_CONTEXT

        # Check membership role
        sender_role = "NON_MEMBER"
        sender_joined_at = 0
        is_muted = False

        if registry.groups_repo:
            member = registry.groups_repo.get_member(group_id, sender_phone_or_id)
            if member:
                sender_role = member.role.value if hasattr(member.role, "value") else str(member.role)
                sender_joined_at = getattr(member, "joined_at_epoch_ms", 0) or 0
                is_muted = getattr(member, "is_muted", False)

        return GroupContext(
            group_id=group.group_id,
            group_name=group.group_name,
            group_type=group.group_type if isinstance(group.group_type, str) else getattr(group.group_type, "value", "COMMUNITY"),
            created_at_timestamp=getattr(group, "created_at_epoch_ms", 0) or 0,
            total_member_count=getattr(group, "total_members", 0) or 0,
            is_announcement_only=getattr(group, "is_announcement_only", False),
            sender_role=sender_role,
            sender_joined_at=sender_joined_at,
            sender_is_muted_in_group=is_muted,
        )


class BusinessContextBuilder:
    """Sub-context builder for BusinessContext models."""

    def build(
        self,
        business_id: str,
        registry: ContextRepositoryRegistry,
        cache: Optional[ContextCache] = None,
    ) -> BusinessContext:
        """Construct BusinessContext instance for business interactions."""
        if not business_id or business_id in ("NONE", ""):
            return DEFAULT_BUSINESS_CONTEXT

        # Check L1 cache
        b_acc = cache.get_business(business_id) if cache else None
        if not b_acc and registry.business_accounts_repo:
            b_acc = registry.business_accounts_repo.get_by_id(business_id)
            if b_acc and cache:
                cache.put_business(business_id, b_acc)

        if not b_acc:
            return DEFAULT_BUSINESS_CONTEXT

        category = getattr(b_acc, "category", "RETAIL")
        category_str = category.value if hasattr(category, "value") else str(category)

        verif = getattr(b_acc, "verification_status", "UNVERIFIED")
        verif_str = verif.value if hasattr(verif, "value") else str(verif)

        return BusinessContext(
            business_id=b_acc.business_id,
            business_name=b_acc.business_name,
            category=category_str,
            verification_status=verif_str,
            support_email=getattr(b_acc, "support_email", "") or "",
            catalog_enabled=getattr(b_acc, "catalog_enabled", False),
            expected_sla_minutes=getattr(b_acc, "expected_sla_minutes", 0) or 0,
            is_business_account=True,
        )


class MediaContextBuilder:
    """Sub-context builder for MediaContext models."""

    def build(
        self,
        payload: RawMessagePayload,
        registry: ContextRepositoryRegistry,
        cache: Optional[ContextCache] = None,
    ) -> MediaContext:
        """Construct MediaContext instance from multimodal cache or defaults."""
        if not payload.media_hash or payload.media_type in ("TEXT", "NONE", ""):
            return DEFAULT_MEDIA_CONTEXT

        # Lookup in cache or multimodal cache
        media_id = payload.media_hash[:12]
        media_type = payload.media_type.upper()

        if registry.multimodal_cache:
            if media_type == "IMAGE":
                ocr_res = registry.multimodal_cache.get_ocr(payload.media_hash)
                vlm_res = registry.multimodal_cache.get_vlm(payload.media_hash)
                summary_res = registry.multimodal_cache.get_summary(payload.media_hash)

                ocr_text = ocr_res.full_extracted_text if ocr_res else ""
                summary = summary_res.get("summary", "") if summary_res else ""
                category = summary_res.get("category", "IMAGE") if summary_res else "IMAGE"
                risk_score = summary_res.get("risk_score", 0.0) if summary_res else 0.0

                return MediaContext(
                    media_id=media_id,
                    media_type="IMAGE",
                    sha256_hash=payload.media_hash,
                    has_media=True,
                    image_summary=summary,
                    image_category=category,
                    ocr_extracted_text=ocr_text,
                    image_risk_score=risk_score,
                    validation_status="VALIDATED",
                )
            elif media_type == "VOICE":
                asr_res = registry.multimodal_cache.get_transcript(payload.media_hash)
                summary_res = registry.multimodal_cache.get_summary(payload.media_hash)

                transcript = asr_res.get("transcript", "") if asr_res else ""
                duration = asr_res.get("duration_seconds", 0.0) if asr_res else 0.0
                tone = asr_res.get("acoustic_tone", "NEUTRAL") if asr_res else "NEUTRAL"
                urgency = asr_res.get("urgency_score", 0.0) if asr_res else 0.0

                return MediaContext(
                    media_id=media_id,
                    media_type="VOICE",
                    sha256_hash=payload.media_hash,
                    has_media=True,
                    voice_transcript=transcript,
                    voice_duration_seconds=duration,
                    acoustic_tone=tone,
                    voice_urgency_score=urgency,
                    validation_status="VALIDATED",
                )

        return MediaContext(
            media_id=media_id,
            media_type=media_type,
            sha256_hash=payload.media_hash,
            has_media=True,
            validation_status="VALIDATED",
        )


class HistoryContextBuilder:
    """Sub-context builder for HistoryContext models."""

    def build(
        self,
        sender_id: str,
        receiver_id: str,
        registry: ContextRepositoryRegistry,
        now_ts_ms: Optional[int] = None,
    ) -> HistoryContext:
        """Construct HistoryContext from history and events repositories."""
        if not registry.message_history_repo:
            return DEFAULT_HISTORY_CONTEXT

        now_ms = now_ts_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
        trajectory = registry.message_history_repo.get_trajectory(receiver_id, sender_id)

        if not trajectory:
            return DEFAULT_HISTORY_CONTEXT

        hist_count = len(trajectory)
        last_item = trajectory[-1]
        last_ts = getattr(last_item, "timestamp_epoch_ms", 0) or 0
        days_since = max(0.0, round((now_ms - last_ts) / (1000.0 * 86400.0), 2)) if last_ts > 0 else 0.0

        events: List[str] = []
        if registry.message_events_repo:
            user_events = registry.message_events_repo.get_user_events(receiver_id)
            events = [getattr(ev, "event_type", "DELIVERED") for ev in user_events[:5]]

        return HistoryContext(
            historical_message_count=hist_count,
            last_interaction_timestamp=last_ts,
            days_since_last_interaction=days_since,
            recent_event_types=events,
            historical_similar_message_count=max(0, hist_count - 1),
        )


class NotificationContextBuilder:
    """Sub-context builder for NotificationContext models."""

    def build(
        self,
        receiver_id: str,
        registry: ContextRepositoryRegistry,
        date_str: Optional[str] = None,
    ) -> NotificationContext:
        """Construct NotificationContext from daily summary repository."""
        if not registry.daily_notification_summary_repo or not receiver_id:
            return DEFAULT_NOTIFICATION_CONTEXT

        date_key = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        summary = registry.daily_notification_summary_repo.get_summary(receiver_id, date_key)

        if not summary:
            return DEFAULT_NOTIFICATION_CONTEXT

        volume = getattr(summary, "total_notifications_sent", 0) or 0
        opened = getattr(summary, "notifications_opened", 0) or 0
        open_rate = round(opened / volume, 2) if volume > 0 else 0.0
        avg_resp = getattr(summary, "avg_response_time_seconds", 0.0) or 0.0

        return NotificationContext(
            user_daily_notification_volume=volume,
            historical_open_rate=open_rate,
            historical_avg_response_seconds=avg_resp,
            daily_notification_cap=50,
        )


class RelationshipContextBuilder:
    """Sub-context builder for RelationshipContext models synthesizing user, business, and group ties."""

    def build(
        self,
        user_ctx: UserContext,
        business_ctx: BusinessContext,
        group_ctx: GroupContext,
        history_ctx: HistoryContext,
        registry: ContextRepositoryRegistry,
        cache: Optional[ContextCache] = None,
    ) -> RelationshipContext:
        """Synthesize relational attributes between sender, recipient, and group/business entities."""
        rel_type = "PEER_TO_PEER"
        total_orders = 0
        total_spend = 0.0
        comm_tier = "NON_CUSTOMER"

        if business_ctx.is_business_account and business_ctx.business_id != "NONE":
            rel_type = "CUSTOMER_BUSINESS"
            if registry.business_accounts_repo:
                hist = registry.business_accounts_repo.get_user_history(user_ctx.user_id, business_ctx.business_id)
                if hist:
                    total_orders = getattr(hist, "total_orders", 0) or 0
                    total_spend = getattr(hist, "total_spend", 0.0) or 0.0

            if total_orders >= 10 or total_spend >= 500.0:
                comm_tier = "VIP"
            elif total_orders >= 1:
                comm_tier = "REGULAR"
            else:
                comm_tier = "NEW"
        elif group_ctx.group_id != "NONE":
            rel_type = "GROUP_MEMBER"

        is_saved = history_ctx.historical_message_count >= 5

        return RelationshipContext(
            relationship_type=rel_type,
            customer_total_orders=total_orders,
            customer_total_spend=total_spend,
            commercial_tier=comm_tier,
            is_contacts_saved=is_saved,
        )


class ConversationContextBuilder:
    """Sub-context builder for ConversationContext thread state."""

    def build(self, payload: RawMessagePayload, group_ctx: GroupContext) -> ConversationContext:
        """Construct ConversationContext thread attributes."""
        is_group = group_ctx.group_id != "NONE"
        conv_id = group_ctx.group_id if is_group else f"DM_{min(payload.sender_phone, payload.receiver_phone)}_{max(payload.sender_phone, payload.receiver_phone)}"

        return ConversationContext(
            conversation_id=conv_id,
            is_group_chat=is_group,
            active_participant_count=group_ctx.total_member_count if is_group else 2,
            burst_message_count=1,
            thread_cadence="EPISODIC",
        )


class BehaviourContextBuilder:
    """Sub-context builder for BehaviourContext statistical patterns."""

    def build(self, payload: RawMessagePayload, history_ctx: HistoryContext) -> BehaviourContext:
        """Compute BehaviourContext user activity habits."""
        daily_avg = round(history_ctx.historical_message_count / 30.0, 2)
        fwd_ratio = 0.5 if payload.is_forwarded else 0.0

        # Check quiet hours (e.g. 22:00 to 07:00)
        dt = datetime.fromtimestamp(payload.timestamp / 1000.0, tz=timezone.utc) if payload.timestamp > 0 else datetime.now(timezone.utc)
        hour = dt.hour
        is_quiet = hour >= 22 or hour < 7

        return BehaviourContext(
            sender_avg_daily_messages=daily_avg,
            sender_forward_ratio=fwd_ratio,
            receiver_quiet_hours_active=is_quiet,
        )
