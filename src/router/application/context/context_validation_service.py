"""Context Validation, Null Handling, and Fallback Validation Service."""


from router.application.context.builder_pipeline import UnvalidatedContextBag
from router.application.context.context_quality_engine import ContextQualityEngine
from router.core.logging.logger import get_logger
from router.domain.entities.context import ContextQualityMetrics
from router.domain.entities.sub_contexts import (
    MediaContext,
)
from router.domain.exceptions import InvalidPayloadException

logger = get_logger(__name__)


class ContextValidationService:
    """Applies structural integrity, referential checks, boundary clamping, and null fallbacks."""

    def __init__(self, quality_engine: Optional[ContextQualityEngine] = None) -> None:
        """Initialize validation service with quality scoring engine."""
        self.quality_engine = quality_engine or ContextQualityEngine()

    def validate(self, bag: UnvalidatedContextBag) -> tuple[UnvalidatedContextBag, ContextQualityMetrics]:
        """Perform 4-stage validation pipeline on unvalidated context bag."""
        # Stage 1: Structural & Schema Validation
        self._validate_structure(bag)

        # Stage 2: Referential Integrity & Link Checks
        self._validate_referential_integrity(bag)

        # Stage 3: Boundary & Value Normalization
        self._normalize_boundaries(bag)

        # Stage 4: Completeness Scoring & Fallback Injection
        quality_metrics = self.quality_engine.compute_quality_score(bag)

        return bag, quality_metrics

    def _validate_structure(self, bag: UnvalidatedContextBag) -> None:
        """Validate mandatory message payload attributes."""
        if not bag.payload.message_id or bag.payload.message_id.strip() == "":
            raise InvalidPayloadException("Incoming message_id is missing or empty.")

    def _validate_referential_integrity(self, bag: UnvalidatedContextBag) -> None:
        """Ensure non-existent entities degrade to default objects gracefully."""
        if not bag.sender.is_registered_user and bag.sender.user_id == "UNKNOWN_USER":
            # Retain DEFAULT_USER_CONTEXT
            pass

        if bag.group.group_id == "NONE" and bag.payload.group_id != "NONE":
            # Orphan group fallback
            logger.warning(f"Orphan group reference {bag.payload.group_id}; applying default group fallback.")

    def _normalize_boundaries(self, bag: UnvalidatedContextBag) -> None:
        """Clamp numerical boundary values between [0.0, 1.0]."""
        if bag.media.has_media:
            # Clamp media scores
            clamped_risk = max(0.0, min(1.0, bag.media.image_risk_score))
            clamped_urgency = max(0.0, min(1.0, bag.media.voice_urgency_score))
            if clamped_risk != bag.media.image_risk_score or clamped_urgency != bag.media.voice_urgency_score:
                bag.media = MediaContext(
                    media_id=bag.media.media_id,
                    media_type=bag.media.media_type,
                    sha256_hash=bag.media.sha256_hash,
                    has_media=bag.media.has_media,
                    image_summary=bag.media.image_summary,
                    image_category=bag.media.image_category,
                    ocr_extracted_text=bag.media.ocr_extracted_text,
                    image_risk_score=clamped_risk,
                    voice_transcript=bag.media.voice_transcript,
                    voice_duration_seconds=bag.media.voice_duration_seconds,
                    acoustic_tone=bag.media.acoustic_tone,
                    voice_urgency_score=clamped_urgency,
                    validation_status=bag.media.validation_status,
                )
