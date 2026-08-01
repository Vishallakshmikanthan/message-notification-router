"""RiskEngine implementation evaluating spam, scam, fraud, and unverified sender risks."""

import math
from typing import Dict

from router.application.signals.base_calculator import BaseSignalCalculator
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalValue

logger = get_logger(__name__)

SCAM_KEYWORDS = {
    "lottery", "prize", "win money", "blocked", "suspended", "verify credential",
    "otp", "click link", "unclaimed bonus", "phish", "scam", "bank account", "urgent cash", "wire"
}
CREDENTIAL_KEYWORDS = {"password", "pin number", "social security", "card number", "cvv", "verification code", "credential"}
FRAUD_KEYWORDS = {"gift card", "crypto", "bitcoin", "wire transfer", "western union", "apple gift card"}


class SpamSignalCalculator(BaseSignalCalculator):
    """Quantifies probability that message is an unsolicited bulk spam broadcast."""

    def get_name(self) -> str:
        return "spam"

    def get_category(self) -> str:
        return "risk"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        no_contact = not context.sender.is_registered_user or not context.relationship.is_contacts_saved
        has_links = context.core_message.contains_links
        past_reports = context.history.historical_similar_message_count
        is_fwd = context.core_message.is_forwarded or context.forwarded_count > 0

        z = (
            1.2 * (1.0 if no_contact else 0.0)
            + 0.8 * (1.0 if has_links else 0.0)
            + 1.5 * min(past_reports, 5)
            + 0.6 * (1.0 if is_fwd else 0.0)
            - 1.8
        )
        score = 1.0 / (1.0 + math.exp(-z))
        conf = 0.90 if no_contact and has_links else 0.70

        return self.create_signal_value(
            score=score,
            confidence=conf,
            raw_value=score,
            primary_driver="unsolicited_broadcast" if score > 0.5 else "clean_message",
            rationale=f"Spam score {score:.2f} (no_contact={no_contact}, links={has_links}, fwd={is_fwd}).",
            contributing_factors={
                "no_contact": 1.0 if no_contact else 0.0,
                "has_links": 1.0 if has_links else 0.0,
                "is_forwarded": 1.0 if is_fwd else 0.0,
            },
        )


class ScamSignalCalculator(BaseSignalCalculator):
    """Identifies phishing, prize scams, and deceptive identity impersonation."""

    def get_name(self) -> str:
        return "scam"

    def get_category(self) -> str:
        return "risk"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        text = (context.core_message.cleaned_text or context.message_text or "").lower()
        raw_text = (context.core_message.raw_text_content or "").lower()
        ocr_text = (context.media.ocr_extracted_text or context.media_ocr_text or "").lower()
        combined = f"{text} {raw_text} {ocr_text}"

        scam_hits = sum(1 for kw in SCAM_KEYWORDS if kw in combined)
        has_cred_req = any(kw in combined for kw in CREDENTIAL_KEYWORDS)
        unverified = not context.sender.is_verified and not context.business.is_business_account

        if not unverified and context.business.verification_status == "VERIFIED_OFFICIAL":
            score = 0.05
            driver = "verified_official_business"
        else:
            score = min(1.0, 0.3 * scam_hits + 0.5 * (1.0 if has_cred_req else 0.0))
            if scam_hits >= 2 or (scam_hits >= 1 and has_cred_req):
                score = max(score, 0.85)
            driver = "scam_phishing_keywords" if score > 0.4 else "clean"

        return self.create_signal_value(
            score=score,
            confidence=0.90 if scam_hits > 0 or has_cred_req else 0.60,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Scam score {score:.2f} based on phishing pattern matching.",
        )


class FraudIndicatorCalculator(BaseSignalCalculator):
    """Detects illicit financial requests, gift card scams, or money transfer coercion."""

    def get_name(self) -> str:
        return "fraud_indicator"

    def get_category(self) -> str:
        return "risk"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        history_count = context.history.historical_message_count
        is_contact = context.relationship.is_contacts_saved

        if history_count > 50 and is_contact:
            score = 0.0
            driver = "trusted_history"
        else:
            text = (context.core_message.cleaned_text or context.message_text or "").lower()
            is_payment = "wire" in text or "transfer" in text or "send money" in text
            is_crypto = any(kw in text for kw in FRAUD_KEYWORDS)

            z = 1.5 * (1.0 if is_payment else 0.0) + 1.2 * (1.0 if is_crypto else 0.0) - 1.0
            score = 1.0 / (1.0 + math.exp(-z)) if (is_payment or is_crypto) else 0.0
            driver = "financial_fraud_request" if score > 0.4 else "none"

        return self.create_signal_value(
            score=score,
            confidence=0.85 if score > 0 else 0.60,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Fraud indicator score {score:.2f}.",
        )


class BusinessTrustRiskCalculator(BaseSignalCalculator):
    """Measures risk rating associated with unverified or deceptive business profiles."""

    def get_name(self) -> str:
        return "business_trust"

    def get_category(self) -> str:
        return "risk"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_biz = context.business.is_business_account or context.business.category != "NON_BUSINESS"
        if not is_biz:
            score = 0.0
            unverified_flag = 0.0
            driver = "non_business"
        elif context.business.verification_status == "VERIFIED_OFFICIAL":
            score = 0.05
            unverified_flag = 0.0
            driver = "verified_official"
        else:
            score = min(1.0, 0.4 + 1.5 * 0.1)
            unverified_flag = 1.0
            driver = "unverified_business"

        return self.create_signal_value(
            score=score,
            confidence=0.85 if is_biz else 0.50,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Business trust risk score {score:.2f}.",
            contributing_factors={"unverified": unverified_flag},
        )


class ForwardChainRiskCalculator(BaseSignalCalculator):
    """Evaluates risk from virally forwarded messages across the network."""

    def get_name(self) -> str:
        return "forward_chain_risk"

    def get_category(self) -> str:
        return "risk"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_fwd = context.core_message.is_forwarded or context.forwarded_count > 0
        fwd_count = max(context.core_message.forward_count, context.forwarded_count)
        is_freq = context.core_message.is_frequently_forwarded or fwd_count >= 5

        score = min(
            1.0,
            0.2 * (1.0 if is_fwd else 0.0)
            + 0.15 * min(fwd_count, 5)
            + 0.3 * (1.0 if is_freq else 0.0),
        )

        return self.create_signal_value(
            score=score,
            confidence=0.90 if is_fwd else 0.60,
            raw_value=score,
            primary_driver="frequently_forwarded" if is_freq else ("forwarded" if is_fwd else "direct"),
            rationale=f"Forward chain risk score {score:.2f} (count={fwd_count}).",
            contributing_factors={"forward_count": float(fwd_count)},
        )


class UnknownSenderRiskCalculator(BaseSignalCalculator):
    """Quantifies exposure risk originating from unsaved or non-reciprocal contacts."""

    def get_name(self) -> str:
        return "unknown_sender_risk"

    def get_category(self) -> str:
        return "risk"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_saved = context.relationship.is_contacts_saved or (context.user is not None)
        is_group = context.conversation.is_group_chat or context.group.group_id != "NONE"

        if is_saved:
            score = 0.0
            driver = "saved_contact"
        elif is_group:
            score = 0.10
            driver = "group_chat_sender"
        else:
            score = 0.85
            driver = "unknown_direct_sender"

        return self.create_signal_value(
            score=score,
            confidence=0.85,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Unknown sender risk score {score:.2f}.",
        )


class VisualScamRiskCalculator(BaseSignalCalculator):
    """Evaluates scam risk embedded in image attachments."""

    def get_name(self) -> str:
        return "visual_scam_risk"

    def get_category(self) -> str:
        return "risk"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        has_img = context.media.has_media and context.media.media_type in {"IMAGE", "MULTIMODAL_COMBO"}
        ocr_text = (context.media.ocr_extracted_text or context.media_ocr_text or "").lower()

        if not has_img and not ocr_text:
            score = 0.0
            driver = "no_image_media"
        else:
            scam_ocr = any(kw in ocr_text for kw in SCAM_KEYWORDS)
            has_qr = "qr" in ocr_text or "scan code" in ocr_text
            z = 1.4 * (1.0 if has_qr else 0.0) + 1.1 * (1.0 if scam_ocr else 0.0) - 1.2
            score = 1.0 / (1.0 + math.exp(-z)) if (has_qr or scam_ocr) else 0.02
            driver = "visual_scam_ocr" if score > 0.4 else "clean_image"

        return self.create_signal_value(
            score=score,
            confidence=0.80 if has_img else 0.50,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Visual scam risk score {score:.2f}.",
        )


class VoiceScamRiskCalculator(BaseSignalCalculator):
    """Evaluates fraud and voice cloning scam indicators from audio voice note transcripts."""

    def get_name(self) -> str:
        return "voice_scam_risk"

    def get_category(self) -> str:
        return "risk"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        has_voice = context.media.has_media and (context.media.media_type == "VOICE" or bool(context.voice_transcript))
        transcript = (context.media.voice_transcript or context.voice_transcript or "").lower()

        if not has_voice and not transcript:
            score = 0.0
            driver = "no_voice_media"
        else:
            urgency_voice = any(kw in transcript for kw in {"arrested", "transfer money", "kidnapped", "hospital bill", "urgent cash"})
            stress_score = context.media.voice_urgency_score or 0.0
            z = 1.3 * (1.0 if urgency_voice else 0.0) + 0.8 * stress_score - 1.1
            score = 1.0 / (1.0 + math.exp(-z)) if urgency_voice else 0.01
            driver = "voice_extortion_scam" if score > 0.4 else "clean_voice"

        return self.create_signal_value(
            score=score,
            confidence=0.75 if has_voice else 0.50,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Voice scam risk score {score:.2f}.",
        )


class RiskEngine(BaseSignalCalculator):
    """Engine coordinating all risk signal calculations."""

    def __init__(self) -> None:
        """Initialize risk calculators."""
        self.calculators = [
            SpamSignalCalculator(),
            ScamSignalCalculator(),
            FraudIndicatorCalculator(),
            BusinessTrustRiskCalculator(),
            ForwardChainRiskCalculator(),
            UnknownSenderRiskCalculator(),
            VisualScamRiskCalculator(),
            VoiceScamRiskCalculator(),
        ]

    def get_name(self) -> str:
        return "risk_engine"

    def get_category(self) -> str:
        return "risk"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        results = {calc.get_name(): calc.calculate_signal(context) for calc in self.calculators}
        max_sig = max(results.values(), key=lambda s: s.score)
        return max_sig

    def calculate_all(self, context: MessageContext) -> Dict[str, SignalValue]:
        """Compute dictionary mapping each risk signal name to its SignalValue."""
        return {calc.get_name(): calc.calculate_signal(context) for calc in self.calculators}
