"""ContextAssembler (ContextAssemblyEngine) entrypoint service orchestrating context building."""

import time
from typing import List, Optional, Union

from router.application.context.builder_pipeline import ParallelContextBuilderPipeline
from router.application.context.context_factory import MessageContextFactory
from router.application.context.context_validation_service import ContextValidationService
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.message import Message
from router.domain.entities.raw_message import RawMessagePayload
from router.domain.exceptions import InvalidPayloadException
from router.infrastructure.cache.context_cache import ContextCache
from router.infrastructure.repositories.context_repository_registry import ContextRepositoryRegistry

logger = get_logger(__name__)


class ContextAssembler:
    """Context Assembly Engine executing the 13-stage deterministic context assembly flow."""

    def __init__(
        self,
        registry: Optional[ContextRepositoryRegistry] = None,
        cache: Optional[ContextCache] = None,
        pipeline: Optional[ParallelContextBuilderPipeline] = None,
        validation_service: Optional[ContextValidationService] = None,
        factory: Optional[MessageContextFactory] = None,
    ) -> None:
        """Initialize ContextAssembler with repository registry, cache, pipeline, validator, and factory."""
        self.registry = registry or ContextRepositoryRegistry()
        self.cache = cache or ContextCache()
        self.pipeline = pipeline or ParallelContextBuilderPipeline()
        self.validation_service = validation_service or ContextValidationService()
        self.factory = factory or MessageContextFactory()

    def assemble(self, raw_message: Union[RawMessagePayload, Message, dict]) -> MessageContext:
        """Assemble a single raw message payload into a fully enriched, immutable MessageContext."""
        t_start = time.perf_counter()

        # Stage 0 & 1: Raw Message Ingestion & Data Validation
        payload = self._normalize_payload(raw_message)

        if not payload.message_id or payload.message_id.strip() == "":
            raise InvalidPayloadException("Corrupted payload: message_id is required.")

        # Stage 2-10: Pre-Hydration & Parallel Sub-Context Assembly
        unvalidated_bag = self.pipeline.execute_parallel(payload, self.registry, self.cache)

        # Stage 11: Completeness & Quality Validation
        validated_bag, metrics = self.validation_service.validate(unvalidated_bag)

        # Stage 12: Object Freezing & Master Emission
        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000.0

        ctx = self.factory.create(validated_bag, metrics, assembly_latency_ms=latency_ms)
        logger.info(
            f"Context assembled successfully for message {payload.message_id} "
            f"in {latency_ms:.2f}ms (Q-score: {metrics.completeness_score:.2f})"
        )
        return ctx

    def assemble_batch(
        self, raw_messages: List[Union[RawMessagePayload, Message, dict]]
    ) -> List[MessageContext]:
        """Assemble a batch of raw message payloads into fully enriched MessageContext objects."""
        return [self.assemble(msg) for msg in raw_messages]

    def _normalize_payload(self, raw_message: Union[RawMessagePayload, Message, dict]) -> RawMessagePayload:
        """Normalize raw input payload (RawMessagePayload, domain Message, or dictionary) into RawMessagePayload."""
        if isinstance(raw_message, RawMessagePayload):
            return raw_message

        if isinstance(raw_message, Message):
            ts_ms = (
                int(raw_message.created_at.timestamp() * 1000)
                if hasattr(raw_message.created_at, "timestamp")
                else 0
            )
            return RawMessagePayload(
                message_id=raw_message.message_id,
                sender_phone=raw_message.sender_id,
                receiver_phone=raw_message.user_id,
                group_id=raw_message.group_id or "NONE",
                business_id=raw_message.business_id or "NONE",
                content=raw_message.message_text or "",
                timestamp=ts_ms,
                media_hash=raw_message.media_id or "",
                media_type=(raw_message.media_type or "TEXT").upper(),
                is_forwarded=raw_message.forwarded_count > 0,
                forward_count=raw_message.forwarded_count,
            )

        if isinstance(raw_message, dict):
            fwd_count = 0
            raw_fwd = raw_message.get("forwarded_count") or raw_message.get("forward_count")
            if raw_fwd:
                try:
                    fwd_count = int(raw_fwd)
                except ValueError:
                    fwd_count = 0

            sender_phone = (
                raw_message.get("sender_user_id")
                or raw_message.get("sender_phone")
                or raw_message.get("sender_id")
                or ""
            )
            receiver_phone = (
                raw_message.get("user_id")
                or raw_message.get("receiver_phone")
                or ""
            )
            content = raw_message.get("message_text") if raw_message.get("message_text") is not None else raw_message.get("content", "")
            media_hash = raw_message.get("media_id") or raw_message.get("media_hash") or ""
            media_type = (raw_message.get("media_type") or "TEXT").upper()

            return RawMessagePayload(
                message_id=raw_message.get("message_id", ""),
                sender_phone=sender_phone,
                receiver_phone=receiver_phone,
                group_id=(raw_message.get("group_id") or "").strip() or "NONE",
                business_id=(raw_message.get("business_id") or "").strip() or "NONE",
                content=content,
                timestamp=raw_message.get("timestamp", 0),
                media_hash=media_hash,
                media_type=media_type,
                is_forwarded=fwd_count > 0 or bool(raw_message.get("is_forwarded", False)),
                forward_count=fwd_count,
            )


        raise InvalidPayloadException(f"Unsupported payload type: {type(raw_message)}")


# Backward-compatibility alias
ContextAssemblyEngine = ContextAssembler
