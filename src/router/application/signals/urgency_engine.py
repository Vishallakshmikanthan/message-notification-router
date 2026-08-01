"""UrgencyEngine implementation computing time-criticality, emergency, payment, meeting, and deadline signals."""

import math
import re
from typing import Dict

from router.application.signals.base_calculator import BaseSignalCalculator
from router.core.logging.logger import get_logger
from router.domain.entities.context import MessageContext
from router.domain.entities.signal import SignalValue

logger = get_logger(__name__)

EMERGENCY_KEYWORDS = {"sos", "help me", "accident", "hospitalized", "911", "call immediately", "emergency", "urgent", "asap", "distress"}
OTP_KEYWORDS = {"otp", "verification code", "one time password", "auth code", "security code", "valid for"}
BILL_KEYWORDS = {"bill overdue", "payment due", "account balance due", "invoice unpaid", "past due"}
PAYMENT_KEYWORDS = {"payment request", "pay back", "wire transfer", "send money"}
MEETING_URL_PATTERN = re.compile(r"https?://(?:meet\.google\.com|zoom\.us|teams\.microsoft\.com|webex\.com)/[a-zA-Z0-9_-]+", re.IGNORECASE)
MEETING_NOW_KEYWORDS = {"starting now", "join now", "standup", "call in progress", "meeting starting"}
HEALTH_KEYWORDS = {"hospital", "doctor", "lab report", "prescription", "glucose", "clinic", "patient", "medical test"}
DEADLINE_TODAY = {"by today", "due today", "today sharp", "by 5 pm", "expires today", "submit today"}
DEADLINE_TOMORROW = {"due tomorrow", "by tomorrow", "expires tomorrow", "submit tomorrow"}


class EmergencySignalCalculator(BaseSignalCalculator):
    """Calculates acute physical danger and emergency distress score."""

    def get_name(self) -> str:
        return "emergency"

    def get_category(self) -> str:
        return "urgency"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        raw_text = context.core_message.raw_text_content or context.message_text or ""
        cleaned = context.core_message.cleaned_text or ""
        voice_text = context.media.voice_transcript or context.voice_transcript or ""
        combined_text = f"{raw_text} {cleaned} {voice_text}".lower()

        has_emerg_kw = any(kw in combined_text for kw in EMERGENCY_KEYWORDS)
        is_family = context.relationship.relationship_type.upper() in {"SPOUSE", "PARENT", "CHILD", "FAMILY"}
        is_high_voice_stress = (
            context.media.acoustic_tone in {"URGENT", "SHOUTING"}
            or context.media.voice_urgency_score >= 0.7
        )

        score = min(
            1.0,
            0.6 * (1.0 if has_emerg_kw else 0.0)
            + 0.3 * (1.0 if is_family else 0.0)
            + 0.3 * (1.0 if is_high_voice_stress else 0.0),
        )
        conf = 0.9 if has_emerg_kw or is_high_voice_stress else 0.7

        return self.create_signal_value(
            score=score,
            confidence=conf,
            raw_value=score,
            primary_driver="emergency_keywords" if has_emerg_kw else "routine",
            rationale=f"Emergency score {score:.2f} based on keywords, family tie, and acoustic stress.",
            contributing_factors={
                "has_keywords": 1.0 if has_emerg_kw else 0.0,
                "is_family": 1.0 if is_family else 0.0,
                "voice_stress": 1.0 if is_high_voice_stress else 0.0,
            },
        )


class TimeSensitiveEventCalculator(BaseSignalCalculator):
    """Calculates proximity of upcoming events using time decay function."""

    def get_name(self) -> str:
        return "time_sensitive_event"

    def get_category(self) -> str:
        return "urgency"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        text = f"{context.core_message.raw_text_content} {context.core_message.cleaned_text} {context.message_text}".lower()
        score = 0.05
        driver = "none"

        if any(kw in text for kw in {"boarding", "flight in", "arriving in", "starting in 10", "starting in 20", "starts in"}):
            score = 0.95
            driver = "imminent_event_keyword"
        elif any(kw in text for kw in {"today", "tonight", "this afternoon", "within an hour"}):
            score = 0.60
            driver = "near_term_keyword"

        return self.create_signal_value(
            score=score,
            confidence=0.85 if driver != "none" else 0.50,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Time sensitive event score {score:.2f} derived from temporal keywords.",
        )


class PaymentUrgencyCalculator(BaseSignalCalculator):
    """Calculates OTP, bill due, and payment request urgency."""

    def get_name(self) -> str:
        return "payment"

    def get_category(self) -> str:
        return "urgency"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        text = f"{context.core_message.raw_text_content} {context.core_message.cleaned_text} {context.message_text}".lower()
        is_otp = any(kw in text for kw in OTP_KEYWORDS)
        is_bill_overdue = any(kw in text for kw in BILL_KEYWORDS)
        is_payment_req = any(kw in text for kw in PAYMENT_KEYWORDS)

        if is_otp:
            score = 1.0
            driver = "otp_code"
        elif is_bill_overdue:
            score = 0.85
            driver = "bill_overdue"
        elif is_payment_req:
            score = 0.60
            driver = "payment_request"
        else:
            score = 0.0
            driver = "none"

        return self.create_signal_value(
            score=score,
            confidence=0.95 if is_otp else (0.85 if is_bill_overdue or is_payment_req else 0.60),
            raw_value=score,
            primary_driver=driver,
            rationale=f"Payment urgency score {score:.2f} (OTP={is_otp}, Bill={is_bill_overdue}).",
            contributing_factors={"is_otp": 1.0 if is_otp else 0.0, "is_bill": 1.0 if is_bill_overdue else 0.0},
        )


class DeadlineUrgencyCalculator(BaseSignalCalculator):
    """Evaluates task or document submission expiry."""

    def get_name(self) -> str:
        return "deadline"

    def get_category(self) -> str:
        return "urgency"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        text = f"{context.core_message.raw_text_content} {context.core_message.cleaned_text} {context.message_text}".lower()
        is_today = any(kw in text for kw in DEADLINE_TODAY)
        is_tomorrow = any(kw in text for kw in DEADLINE_TOMORROW)

        z = 2.0 * (1.0 if is_today else 0.0) + 1.2 * (1.0 if is_tomorrow else 0.0) - 0.5
        score = 1.0 / (1.0 + math.exp(-z)) if (is_today or is_tomorrow) else 0.10
        driver = "today_deadline" if is_today else ("tomorrow_deadline" if is_tomorrow else "none")

        return self.create_signal_value(
            score=score,
            confidence=0.85 if driver != "none" else 0.50,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Deadline urgency score {score:.2f} for task expiry.",
        )


class MeetingUrgencyCalculator(BaseSignalCalculator):
    """Detects live conference calls, video meeting links, or schedule changes."""

    def get_name(self) -> str:
        return "meeting"

    def get_category(self) -> str:
        return "urgency"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        raw_text = context.core_message.raw_text_content or context.message_text or ""
        cleaned = context.core_message.cleaned_text or ""
        has_link = bool(MEETING_URL_PATTERN.search(raw_text)) or context.core_message.contains_links
        
        combined_lower = f"{raw_text} {cleaned}".lower()
        has_meeting_domain = any(dom in combined_lower for dom in ["meet.google", "zoom.us", "teams.microsoft", "webex"])
        has_link = has_link or has_meeting_domain

        starting_now = any(kw in combined_lower for kw in MEETING_NOW_KEYWORDS)
        schedule_change = "rescheduled" in combined_lower or "postponed" in combined_lower or "moved to" in combined_lower

        score = min(
            1.0,
            0.5 * (1.0 if has_link else 0.0)
            + 0.4 * (1.0 if starting_now else 0.0)
            + 0.2 * (1.0 if schedule_change else 0.0),
        )

        return self.create_signal_value(
            score=score,
            confidence=0.90 if has_link else 0.60,
            raw_value=score,
            primary_driver="meeting_link" if has_link else ("starting_now" if starting_now else "none"),
            rationale=f"Meeting urgency score {score:.2f} (link={has_link}, starting_now={starting_now}).",
        )


class AppointmentUrgencyCalculator(BaseSignalCalculator):
    """Evaluates healthcare, service, or courier delivery appointment alerts."""

    def get_name(self) -> str:
        return "appointment"

    def get_category(self) -> str:
        return "urgency"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        text = f"{context.core_message.raw_text_content} {context.core_message.cleaned_text} {context.message_text}".lower()
        is_doctor = "doctor" in text or "clinic appointment" in text or "dentist" in text
        is_delivery = "out for delivery" in text or "courier arriving" in text or "driver arriving" in text
        is_service = "service confirmed" in text or "appointment confirmed" in text

        if is_doctor:
            score = 0.90
            driver = "doctor_appointment"
        elif is_delivery:
            score = 0.80
            driver = "courier_delivery"
        elif is_service:
            score = 0.50
            driver = "service_confirmed"
        else:
            score = 0.05
            driver = "none"

        return self.create_signal_value(
            score=score,
            confidence=0.85 if driver != "none" else 0.50,
            raw_value=score,
            primary_driver=driver,
            rationale=f"Appointment urgency score {score:.2f}.",
        )


class FamilyEmergencyCalculator(BaseSignalCalculator):
    """Measures emergency distress calls originating specifically from family members."""

    def get_name(self) -> str:
        return "family_emergency"

    def get_category(self) -> str:
        return "urgency"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        emerg_calc = EmergencySignalCalculator()
        emerg_val = emerg_calc.calculate_signal(context)

        rel_type = context.relationship.relationship_type.upper()
        if rel_type in {"SPOUSE", "PARENT", "CHILD"}:
            multiplier = 1.0
        elif rel_type == "FAMILY" or rel_type == "EXTENDED_FAMILY":
            multiplier = 0.6
        else:
            multiplier = 0.0

        score = emerg_val.score * multiplier
        return self.create_signal_value(
            score=score,
            confidence=emerg_val.confidence * (1.0 if multiplier > 0 else 0.5),
            raw_value=score,
            primary_driver="family_distress" if score > 0 else "none",
            rationale=f"Family emergency score {score:.2f} (relationship={rel_type}).",
        )


class HealthEmergencyCalculator(BaseSignalCalculator):
    """Detects acute medical alerts, hospital reports, or wellness emergencies."""

    def get_name(self) -> str:
        return "health_emergency"

    def get_category(self) -> str:
        return "urgency"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        text = f"{context.core_message.raw_text_content} {context.core_message.cleaned_text} {context.message_text}".lower()
        has_health_kw = any(kw in text for kw in HEALTH_KEYWORDS)
        is_healthcare_sender = context.business.category.upper() in {"HEALTHCARE", "HOSPITAL", "CLINIC"}

        score = min(1.0, 0.7 * (1.0 if has_health_kw else 0.0) + 0.3 * (1.0 if is_healthcare_sender else 0.0))
        return self.create_signal_value(
            score=score,
            confidence=0.85 if has_health_kw else 0.50,
            raw_value=score,
            primary_driver="health_keywords" if has_health_kw else "none",
            rationale=f"Health emergency score {score:.2f}.",
        )


class CriticalAnnouncementCalculator(BaseSignalCalculator):
    """Measures high-priority organizational or group emergency broadcast notices."""

    def get_name(self) -> str:
        return "critical_announcement"

    def get_category(self) -> str:
        return "urgency"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        is_admin = (
            context.group.sender_role.upper() == "ADMIN"
            or getattr(context, "is_admin_message", False)
            or (context.group_member is not None and getattr(context.group_member, "is_admin", False))
        )
        text = f"{context.core_message.raw_text_content} {context.core_message.cleaned_text} {context.message_text}".lower()
        has_all = "@everyone" in text or "@all" in text or "attention all" in text
        has_urgent_kw = any(kw in text for kw in {"office closed", "emergency alert", "weather alert", "critical update", "all hands"})

        if not is_admin:
            score = 0.15 if has_all else 0.0
        else:
            z = 1.5 * (1.0 if has_all else 0.0) + 1.2 * (1.0 if has_urgent_kw else 0.0) - 1.0
            score = 1.0 / (1.0 + math.exp(-z)) if (has_all or has_urgent_kw) else 0.30

        return self.create_signal_value(
            score=score,
            confidence=0.90 if is_admin and (has_all or has_urgent_kw) else 0.50,
            raw_value=score,
            primary_driver="admin_broadcast" if is_admin and score > 0.5 else "none",
            rationale=f"Critical announcement score {score:.2f} (admin={is_admin}, mention_all={has_all}).",
        )


class UrgencyEngine(BaseSignalCalculator):
    """Engine coordinating all urgency signal calculations."""

    def __init__(self) -> None:
        """Initialize urgency calculators."""
        self.calculators = [
            EmergencySignalCalculator(),
            TimeSensitiveEventCalculator(),
            PaymentUrgencyCalculator(),
            DeadlineUrgencyCalculator(),
            MeetingUrgencyCalculator(),
            AppointmentUrgencyCalculator(),
            FamilyEmergencyCalculator(),
            HealthEmergencyCalculator(),
            CriticalAnnouncementCalculator(),
        ]

    def get_name(self) -> str:
        return "urgency_engine"

    def get_category(self) -> str:
        return "urgency"

    def calculate_signal(self, context: MessageContext) -> SignalValue:
        results = {calc.get_name(): calc.calculate_signal(context) for calc in self.calculators}
        max_sig = max(results.values(), key=lambda s: s.score)
        return max_sig

    def calculate_all(self, context: MessageContext) -> Dict[str, SignalValue]:
        """Compute dictionary mapping each urgency signal name to its SignalValue."""
        return {calc.get_name(): calc.calculate_signal(context) for calc in self.calculators}
