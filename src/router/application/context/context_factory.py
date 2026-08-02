"""MessageContextFactory for instantiating frozen, validated MessageContext master objects."""

import re
import uuid
from datetime import UTC, datetime

from router.application.context.builder_pipeline import UnvalidatedContextBag
from router.core.logging.logger import get_logger
from router.domain.entities.context import (
    ContextMetadata,
    ContextQualityMetrics,
    CoreMessageContext,
    MessageContext,
    TemporalInformation,
)

logger = get_logger(__name__)


class MessageContextFactory:
    """Factory creating fully enriched, validated, immutable master MessageContext instances."""

    URL_REGEX = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
    PHONE_REGEX = re.compile(r"\+?\d{7,15}")


    def create(
        self,
        bag: UnvalidatedContextBag,
        metrics: ContextQualityMetrics,
        assembly_latency_ms: float = 0.0,
    ) -> MessageContext:
        """Instantiate sealed MessageContext instance from validated context bag and quality metrics."""
        now_dt = datetime.now(UTC)
        context_id = f"ctx_{uuid.uuid4().hex[:12]}"

        # 1. Metadata
        metadata = ContextMetadata(
            context_id=context_id,
            assembled_at=now_dt.isoformat(),
            assembly_latency_ms=round(assembly_latency_ms, 2),
            completeness_score=metrics.completeness_score,
        )

        # 2. Core Message
        raw_text = bag.payload.content or ""
        cleaned_text = " ".join(raw_text.split())
        words = [w for w in cleaned_text.split() if w]
        char_count = len(raw_text)
        word_count = len(words)
        contains_links = bool(self.URL_REGEX.search(raw_text))
        contains_phones = bool(self.PHONE_REGEX.search(raw_text))
        is_freq_fwd = bag.payload.forward_count >= 5

        core_msg = CoreMessageContext(
            message_id=bag.payload.message_id,
            raw_text_content=raw_text,
            cleaned_text=cleaned_text,
            message_type=bag.payload.media_type,
            char_count=char_count,
            word_count=word_count,
            contains_links=contains_links,
            contains_phone_numbers=contains_phones,
            is_forwarded=bag.payload.is_forwarded,
            forward_count=bag.payload.forward_count,
            is_frequently_forwarded=is_freq_fwd,
        )

        # 3. Temporal Information
        ts_ms = bag.payload.timestamp if bag.payload.timestamp > 0 else int(now_dt.timestamp() * 1000)
        ts_dt = datetime.fromtimestamp(ts_ms / 1000.0, tz=UTC)
        iso_ts = ts_dt.isoformat()
        day_of_week = ts_dt.strftime("%A").upper()
        hour_of_day = ts_dt.hour
        is_weekend = ts_dt.weekday() in (5, 6)
        is_working = (not is_weekend) and (9 <= hour_of_day < 17)

        temporal = TemporalInformation(
            timestamp_epoch_ms=ts_ms,
            iso_timestamp=iso_ts,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day,
            is_weekend=is_weekend,
            is_working_hours=is_working,
        )

        # 4. Construct Master MessageContext
        return MessageContext(
            context_metadata=metadata,
            core_message=core_msg,
            temporal_info=temporal,
            sender=bag.sender,
            receiver=bag.receiver,
            conversation=bag.conversation,
            group=bag.group,
            business=bag.business,
            media=bag.media,
            history=bag.history,
            notification_behaviour=bag.notification_behaviour,
            relationship=bag.relationship,
            behaviour_stats=bag.behaviour_stats,
            quality_metrics=metrics,

            # Backward compatibility fields
            message_id=bag.payload.message_id,
            user_id=bag.receiver.user_id,
            sender_id=bag.sender.user_id,
            conversation_type="group" if bag.conversation.is_group_chat else ("business" if bag.business.is_business_account else "personal"),
            message_text=raw_text,
            created_at=ts_dt,
            forwarded_count=bag.payload.forward_count,
            media_id=bag.media.media_id,
            media_type=bag.media.media_type.lower() if bag.media.has_media else None,
            media_ocr_text=bag.media.ocr_extracted_text or None,
            voice_transcript=bag.media.voice_transcript or None,
            voice_duration_seconds=bag.media.voice_duration_seconds,
        )
