"""Context Quality & Completeness Scoring Engine implementing mathematical Q-score formula."""


from router.application.context.builder_pipeline import UnvalidatedContextBag
from router.core.logging.logger import get_logger
from router.domain.entities.context import ContextQualityMetrics

logger = get_logger(__name__)


class ContextQualityEngine:
    """Evaluates data density and structural completeness of context objects."""

    WEIGHTS = {
        "user": 0.20,
        "core_message": 0.20,
        "media": 0.15,
        "history": 0.10,
        "group": 0.10,
        "business": 0.10,
        "relationship": 0.10,
        "notification": 0.05,
    }

    def compute_quality_score(self, bag: UnvalidatedContextBag) -> ContextQualityMetrics:
        """Calculate global completeness metric Q in [0.0, 1.0] and sub-context scores."""
        scores: dict[str, float] = {}
        missing_fields: list[str] = []
        warnings: list[str] = []

        # 1. User Context (0.20)
        if bag.sender.is_registered_user and bag.receiver.is_registered_user:
            scores["user"] = 1.0
        elif bag.sender.is_registered_user or bag.receiver.is_registered_user:
            scores["user"] = 0.65
            missing_fields.append("receiver_profile" if bag.sender.is_registered_user else "sender_profile")
        else:
            scores["user"] = 0.25
            warnings.append("Unregistered sender and receiver profiles")

        # 2. Core Message Context (0.20)
        if bag.payload.message_id and (bag.payload.content or bag.payload.media_hash):
            scores["core_message"] = 1.0
        elif bag.payload.message_id:
            scores["core_message"] = 0.50
            missing_fields.append("message_content")
        else:
            scores["core_message"] = 0.0
            warnings.append("Corrupted message payload")

        # 3. Media Context (0.15)
        if not bag.media.has_media or bag.media.media_type == "TEXT_ONLY" or bag.media.validation_status == "VALIDATED":
            scores["media"] = 1.0
        elif bag.media.validation_status == "PARTIAL":
            scores["media"] = 0.50
            warnings.append("Partial media processing extraction")
        else:
            scores["media"] = 0.0
            warnings.append("Corrupted or unresolvable media attachment")

        # 4. History Context (0.10)
        if bag.history.historical_message_count > 0:
            scores["history"] = 1.0
        else:
            scores["history"] = 0.20
            missing_fields.append("historical_trajectory")

        # 5. Group Context (0.10)
        if bag.group.group_id == "NONE" or bag.group.sender_role != "NON_MEMBER":
            scores["group"] = 1.0
        else:
            scores["group"] = 0.50
            warnings.append("Sender unindexed in group membership")

        # 6. Business Context (0.10)
        if bag.business.business_id == "NONE" or bag.business.verification_status != "UNVERIFIED":
            scores["business"] = 1.0
        else:
            scores["business"] = 0.60
            missing_fields.append("business_verification")

        # 7. Relationship Context (0.10)
        if bag.relationship.relationship_type != "UNKNOWN":
            scores["relationship"] = 1.0
        else:
            scores["relationship"] = 0.50

        # 8. Notification Context (0.05)
        if bag.notification_behaviour.user_daily_notification_volume > 0:
            scores["notification"] = 1.0
        else:
            scores["notification"] = 0.40

        # Compute weighted sum Q = sum(w_i * C_i)
        global_q = sum(self.WEIGHTS[k] * scores[k] for k in self.WEIGHTS)
        global_q = max(0.0, min(1.0, round(global_q, 4)))

        is_anon = not bag.sender.is_registered_user

        return ContextQualityMetrics(
            completeness_score=global_q,
            sub_context_scores=scores,
            is_anonymous_sender=is_anon,
            missing_fields=missing_fields,
            validation_warnings=warnings,
        )
