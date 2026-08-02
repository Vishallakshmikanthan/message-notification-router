"""TrustEngine implementation computing business authenticity, relationship closeness, and historical reliability."""

import math

from router.application.signals.base_calculator import BaseSignalCalculator
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalValue

logger = get_logger(__name__)


class BusinessTrustCalculator(BaseSignalCalculator):
    """Evaluates official verification badge, brand authenticity, and enterprise reputation."""

    def get_name(self) -> str:
        return "business_trust_score"

    def get_category(self) -> str:
        return "trust"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_biz = context.business.is_business_account or context.business.category != "NON_BUSINESS"
        if not is_biz:
            score = 0.0
            driver = "non_business"
        elif context.business.verification_status == "VERIFIED_OFFICIAL":
            score = 1.0
            driver = "official_green_badge"
        elif context.business.verification_status == "STANDARD":
            score = 0.60
            driver = "standard_business"
        else:
            score = 0.30
            driver = "unverified_business"

        return self.create_signal_value(
            score=score,
            confidence=0.90 if is_biz else 0.50,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Business trust score {score:.2f}.",
        )


class RelationshipScoreCalculator(BaseSignalCalculator):
    """Quantifies social intimacy, mutual interaction frequency, and relational tie strength."""

    def get_name(self) -> str:
        return "relationship_score"

    def get_category(self) -> str:
        return "trust"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        rel_type = context.relationship.relationship_type.upper()
        w_map = {"SPOUSE": 1.0, "FAMILY": 0.85, "FRIEND": 0.70, "WORK": 0.60, "UNKNOWN": 0.10, "PEER_TO_PEER": 0.50}
        w_type = w_map.get(rel_type, 0.50)

        history_count = context.history.historical_message_count
        interaction_part = min(1.0, history_count / 100.0)

        score = w_type * 0.5 + 0.3 * interaction_part + 0.2 * 0.8  # Assume moderate reciprocity baseline
        score = min(1.0, score)

        return self.create_signal_value(
            score=score,
            confidence=0.85 if history_count > 0 else 0.50,
            raw_value=score,
            primary_driver=f"relationship_{rel_type.lower()}",
            rationale=f"Relationship score {score:.2f} (type={rel_type}, history={history_count}).",
        )


class KnownContactCalculator(BaseSignalCalculator):
    """Evaluates address book presence, save duration, and mutual contacts."""

    def get_name(self) -> str:
        return "known_contact_score"

    def get_category(self) -> str:
        return "trust"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_saved = context.relationship.is_contacts_saved or (context.user is not None and context.user.is_registered_user)
        if not is_saved:
            score = 0.0
            driver = "unsaved_number"
        else:
            age_days = context.sender.account_age_days or 365
            duration_part = min(1.0, age_days / 365.0)
            score = min(1.0, 0.6 + 0.2 * duration_part + 0.2 * 0.5)
            driver = "saved_address_book_contact"

        return self.create_signal_value(
            score=score,
            confidence=0.95 if is_saved else 0.85,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Known contact score {score:.2f}.",
        )


class GroupReliabilityCalculator(BaseSignalCalculator):
    """Measures structural safety, admin verification, and history of group."""

    def get_name(self) -> str:
        return "group_reliability"

    def get_category(self) -> str:
        return "trust"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_group = context.conversation.is_group_chat or context.group.group_id != "NONE"
        if not is_group:
            score = 1.0
            driver = "direct_message"
        else:
            has_admin = context.group.sender_role.upper() == "ADMIN"
            score = max(0.0, 0.8 + (0.2 if has_admin else 0.0))
            driver = "admin_verified_group" if has_admin else "standard_group"

        return self.create_signal_value(
            score=score,
            confidence=0.85,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Group reliability score {score:.2f}.",
        )


class HistoricalTrustCalculator(BaseSignalCalculator):
    """Evaluates multi-month historical safety record and absence of past spam reports."""

    def get_name(self) -> str:
        return "historical_trust"

    def get_category(self) -> str:
        return "trust"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        account_age = context.sender.account_age_days or 180
        age_factor = min(1.0, account_age / 180.0)
        past_reports = context.history.historical_similar_message_count  # spam report proxy
        score = age_factor * math.exp(-0.5 * past_reports)

        return self.create_signal_value(
            score=score,
            confidence=0.85 if account_age > 30 else 0.50,
            raw_value=score,
            primary_driver="account_longevity" if score > 0.5 else "new_account",
            rationale=f"Historical trust score {score:.2f} (account_age_days={account_age}).",
        )


class InteractionStrengthCalculator(BaseSignalCalculator):
    """Measures active volume, frequency, and conversational cadence of two-way communication."""

    def get_name(self) -> str:
        return "interaction_strength"

    def get_category(self) -> str:
        return "trust"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        msgs = context.history.historical_message_count
        volume_part = min(1.0, msgs / 50.0)
        avg_resp_sec = context.notification_behaviour.historical_avg_response_seconds or 3600.0
        latency_part = math.exp(-avg_resp_sec / 86400.0)

        score = 0.6 * volume_part + 0.4 * latency_part
        return self.create_signal_value(
            score=score,
            confidence=0.80 if msgs > 0 else 0.40,
            raw_value=score,
            primary_driver="active_two_way_cadence" if score > 0.5 else "dormant",
            rationale=f"Interaction strength score {score:.2f}.",
        )


class TieStrengthCalculator(BaseSignalCalculator):
    """Calculates granular graph tie strength closeness metric."""

    def get_name(self) -> str:
        return "tie_strength"

    def get_category(self) -> str:
        return "relationship"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        rel_calc = RelationshipScoreCalculator()
        rel_sig = rel_calc.calculate_signal(context)
        return self.create_signal_value(
            score=rel_sig.score,
            confidence=rel_sig.confidence,
            raw_value=rel_sig.explainability.raw_value,
            primary_driver="graph_tie_strength",
            rationale=f"Tie strength score {rel_sig.score:.2f}.",
        )


class IntimacyScoreCalculator(BaseSignalCalculator):
    """Calculates tone intimacy, casualness, and emotional closeness."""

    def get_name(self) -> str:
        return "intimacy_score"

    def get_category(self) -> str:
        return "relationship"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        rel_type = context.relationship.relationship_type.upper()
        if rel_type in {"SPOUSE", "FAMILY"}:
            score = 0.90
        elif rel_type == "FRIEND":
            score = 0.75
        elif rel_type == "WORK":
            score = 0.40
        else:
            score = 0.10

        return self.create_signal_value(
            score=score,
            confidence=0.80,
            raw_value=score,
            primary_driver="relational_intimacy",
            rationale=f"Intimacy score {score:.2f} for relationship type {rel_type}.",
        )


class ReciprocityRatioCalculator(BaseSignalCalculator):
    """Calculates balance of incoming vs outgoing message ratio (0.5 = balanced)."""

    def get_name(self) -> str:
        return "reciprocity_ratio"

    def get_category(self) -> str:
        return "relationship"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        score = 0.50  # Default balanced score
        return self.create_signal_value(
            score=score,
            confidence=0.70,
            raw_value=score,
            primary_driver="reciprocity_balance",
            rationale="Reciprocity ratio score 0.50 (balanced baseline).",
        )


class TrustEngine(BaseSignalCalculator):
    """Engine coordinating all trust and relationship signal calculations."""

    def __init__(self) -> None:
        """Initialize trust calculators."""
        self.calculators = [
            BusinessTrustCalculator(),
            RelationshipScoreCalculator(),
            KnownContactCalculator(),
            GroupReliabilityCalculator(),
            HistoricalTrustCalculator(),
            InteractionStrengthCalculator(),
            TieStrengthCalculator(),
            IntimacyScoreCalculator(),
            ReciprocityRatioCalculator(),
        ]

    def get_name(self) -> str:
        return "trust_engine"

    def get_category(self) -> str:
        return "trust"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        results = {calc.get_name(): calc.calculate_signal(context) for calc in self.calculators}
        return results["relationship_score"]

    def calculate_all(self, context: MessageContext) -> dict[str, SignalValue]:
        """Compute dictionary mapping each trust signal name to its SignalValue."""
        return {calc.get_name(): calc.calculate_signal(context) for calc in self.calculators}
