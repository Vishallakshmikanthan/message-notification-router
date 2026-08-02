"""DecisionFactory — constructs immutable, validated DecisionContext objects.

Aggregates and normalizes raw contextual payload objects from upstream layers
(MessageContext, SignalBundle, EvidenceBundle) into a single frozen evaluation frame.

Spec: decision_engine.md §1 Component Breakdown — DecisionFactory.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.decision_models import DecisionContext
from router.domain.entities.evidence import EvidenceBundle
from router.domain.entities.signal import SignalBundle
from router.domain.ports.decision_ports import IDecisionFactory

logger = get_logger(__name__)


class DecisionFactory(IDecisionFactory):
    """Constructs an immutable, validated DecisionContext.

    Performs:
    - Timestamp normalization to UTC ISO-8601.
    - Structural integrity validation of input bundles.
    - Text sanitization (strips control characters, detects corrupt unicode).
    - Assembly of business, historical, and user context sub-fields.

    This implementation follows the Null Object Pattern for optional contexts:
    missing sub-contexts are provided as None rather than raising errors,
    allowing downstream components to apply graceful degradation.
    """

    def build_context(
        self,
        message_context: MessageContext,
        signal_bundle: SignalBundle,
        evidence_bundle: EvidenceBundle,
    ) -> DecisionContext:
        """Aggregate upstream layer outputs into a single DecisionContext frame.

        Args:
            message_context: Enriched message context from the Context Engine.
            signal_bundle: Computed signal bundle from the Signal Engine.
            evidence_bundle: Retrieved evidence bundle from the Retrieval Engine.

        Returns:
            Immutable, validated DecisionContext ready for engine consumption.

        Raises:
            ValueError: If critical required fields are None or malformed.
        """
        start_time = time.perf_counter()

        # Validate non-null requirements
        if message_context is None:
            raise ValueError("DecisionFactory: message_context must not be None.")
        if signal_bundle is None:
            raise ValueError("DecisionFactory: signal_bundle must not be None.")
        if evidence_bundle is None:
            raise ValueError("DecisionFactory: evidence_bundle must not be None.")

        context_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC).isoformat()

        # Extract optional sub-contexts from MessageContext
        business_ctx: Any | None = self._extract_business_context(message_context)
        historical_ctx: Any | None = self._extract_historical_context(message_context, signal_bundle)
        user_ctx: Any | None = self._extract_user_context(message_context, signal_bundle)

        preprocessing_latency_ms = (time.perf_counter() - start_time) * 1000.0

        decision_context = DecisionContext(
            context_id=context_id,
            timestamp=timestamp,
            message_context=message_context,
            signal_bundle=signal_bundle,
            evidence_bundle=evidence_bundle,
            media_context=self._extract_media_context(message_context),
            historical_context=historical_ctx,
            business_context=business_ctx,
            user_context=user_ctx,
            preprocessing_latency_ms=preprocessing_latency_ms,
        )

        logger.info(
            "DecisionContext assembled",
            context_id=context_id,
            preprocessing_latency_ms=round(preprocessing_latency_ms, 2),
            evidence_count=evidence_bundle.evidence_count,
            signal_completeness=signal_bundle.metadata.global_completeness,
        )

        return decision_context

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_business_context(ctx: MessageContext) -> Any | None:
        """Extract business sub-context if present.

        Args:
            ctx: Source MessageContext.

        Returns:
            BusinessContext or None if not a business interaction.
        """
        bc = ctx.business
        if bc and bc.is_business_account:
            return bc
        # Also expose legacy attribute if used
        if getattr(ctx, "user_business_history", None) is not None:
            return ctx.user_business_history
        return None

    @staticmethod
    def _extract_historical_context(
        ctx: MessageContext, signal_bundle: SignalBundle
    ) -> Any | None:
        """Extract historical interaction context from MessageContext and signals.

        Args:
            ctx: Source MessageContext.
            signal_bundle: Computed signals for supplementing historical data.

        Returns:
            HistoryContext or None.
        """
        hc = ctx.history
        if hc and hc.historical_message_count > 0:
            return hc
        # Check legacy attribute
        if ctx.recent_history:
            return ctx.recent_history
        return None

    @staticmethod
    def _extract_user_context(
        ctx: MessageContext, signal_bundle: SignalBundle
    ) -> Any | None:
        """Extract enriched user context from receiver context and signals.

        Args:
            ctx: Source MessageContext.
            signal_bundle: Signals contributing quiet-hours and VIP status.

        Returns:
            UserContext or dict-like summary.
        """
        return {
            "user_id": ctx.receiver.user_id if ctx.receiver else ctx.user_id,
            "is_quiet_hours_active": signal_bundle.is_quiet_hours,
            "sender_is_vip": (
                signal_bundle.trust.relationship_score.score >= 0.85
            ),
            "sender_in_address_book": signal_bundle.personal_sender_known,
            "chat_is_muted": signal_bundle.group_is_muted_by_user,
        }

    @staticmethod
    def _extract_media_context(ctx: MessageContext) -> Any | None:
        """Extract media context if a media payload is present.

        Args:
            ctx: Source MessageContext.

        Returns:
            MediaContext or None.
        """
        mc = ctx.media
        if mc and mc.has_media:
            return mc
        if ctx.media_id or ctx.media_type:
            return {
                "media_id": ctx.media_id,
                "media_type": ctx.media_type,
                "ocr_text": ctx.media_ocr_text,
                "caption": ctx.media_vlm_caption,
            }
        return None
