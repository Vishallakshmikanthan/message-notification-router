"""Parallel Context Builder Pipeline and transient UnvalidatedContextBag container."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from router.application.context.sub_builders import (
    BehaviourContextBuilder,
    BusinessContextBuilder,
    ConversationContextBuilder,
    GroupContextBuilder,
    HistoryContextBuilder,
    MediaContextBuilder,
    NotificationContextBuilder,
    RelationshipContextBuilder,
    UserContextBuilder,
)
from router.core.logging.logger import get_logger
from router.domain.entities.raw_message import RawMessagePayload
from router.domain.entities.sub_contexts import (
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


@dataclass
class UnvalidatedContextBag:
    """Transient mutable collection object holding sub-contexts prior to validation."""

    payload: RawMessagePayload
    sender: UserContext
    receiver: UserContext
    group: GroupContext
    business: BusinessContext
    media: MediaContext
    history: HistoryContext
    notification_behaviour: NotificationContext
    relationship: RelationshipContext
    conversation: ConversationContext
    behaviour_stats: BehaviourContext


class ParallelContextBuilderPipeline:
    """Orchestrates independent worker units to construct sub-contexts concurrently."""

    def __init__(self, max_workers: int = 8) -> None:
        """Initialize worker builders and thread pool execution pool."""
        self.user_builder = UserContextBuilder()
        self.group_builder = GroupContextBuilder()
        self.business_builder = BusinessContextBuilder()
        self.media_builder = MediaContextBuilder()
        self.history_builder = HistoryContextBuilder()
        self.notification_builder = NotificationContextBuilder()
        self.relationship_builder = RelationshipContextBuilder()
        self.conversation_builder = ConversationContextBuilder()
        self.behaviour_builder = BehaviourContextBuilder()
        self.max_workers = max_workers

    def execute_parallel(
        self,
        payload: RawMessagePayload,
        registry: ContextRepositoryRegistry,
        cache: ContextCache | None = None,
    ) -> UnvalidatedContextBag:
        """Execute Stage 1 independent builders concurrently, followed by Stage 2 dependent synthesis."""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Stage 1: Parallel Dispatch
            f_sender = executor.submit(
                self.user_builder.build, payload.sender_phone, registry, cache, payload.timestamp
            )
            f_receiver = executor.submit(
                self.user_builder.build, payload.receiver_phone, registry, cache, payload.timestamp
            )
            f_group = executor.submit(
                self.group_builder.build, payload.group_id, payload.sender_phone, registry, cache
            )
            f_business = executor.submit(
                self.business_builder.build, payload.business_id, registry, cache
            )
            f_media = executor.submit(self.media_builder.build, payload, registry, cache)
            f_history = executor.submit(
                self.history_builder.build,
                payload.sender_phone,
                payload.receiver_phone,
                registry,
                payload.timestamp,
            )
            f_notification = executor.submit(
                self.notification_builder.build, payload.receiver_phone, registry
            )

            sender = f_sender.result()
            receiver = f_receiver.result()
            group = f_group.result()
            business = f_business.result()
            media = f_media.result()
            history = f_history.result()
            notification_behaviour = f_notification.result()

        # Dependent builders (Conversation & Behaviour)
        conversation = self.conversation_builder.build(payload, group)
        behaviour_stats = self.behaviour_builder.build(payload, history)

        # Stage 2: Dependent Synthesis (Relationship)
        relationship = self.relationship_builder.build(
            receiver, business, group, history, registry, cache
        )

        return UnvalidatedContextBag(
            payload=payload,
            sender=sender,
            receiver=receiver,
            group=group,
            business=business,
            media=media,
            history=history,
            notification_behaviour=notification_behaviour,
            relationship=relationship,
            conversation=conversation,
            behaviour_stats=behaviour_stats,
        )
