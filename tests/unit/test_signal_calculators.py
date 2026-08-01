"""Unit tests for individual categorical signal calculators."""

from router.application.signals.behaviour_engine import BehaviourEngine, NotificationFatigueCalculator
from router.application.signals.personalization_engine import GreetingDetectionCalculator, PersonalizationEngine, QuietHoursCalculator
from router.application.signals.risk_engine import RiskEngine, ScamSignalCalculator, SpamSignalCalculator, UnknownSenderRiskCalculator
from router.application.signals.trust_engine import BusinessTrustCalculator, KnownContactCalculator, TrustEngine
from router.application.signals.urgency_engine import EmergencySignalCalculator, MeetingUrgencyCalculator, PaymentUrgencyCalculator, UrgencyEngine
from router.domain.entities.context import CoreMessageContext, MessageContext, TemporalInformation
from router.domain.entities.sub_contexts import BusinessContext, MediaContext, NotificationContext, RelationshipContext, UserContext


def test_emergency_signal_calculator() -> None:
    """Test emergency signal calculator with distress keywords."""
    calc = EmergencySignalCalculator()

    ctx_emerg = MessageContext(
        core_message=CoreMessageContext(
            message_id="m1",
            raw_text_content="SOS help me accident hospitalized",
            cleaned_text="sos help me accident hospitalized",
            message_type="TEXT",
            char_count=35,
            word_count=5,
            contains_links=False,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        ),
        relationship=RelationshipContext(relationship_type="SPOUSE"),
    )
    sig_emerg = calc.calculate_signal(ctx_emerg)
    assert sig_emerg.score >= 0.8
    assert sig_emerg.explainability.primary_driver == "emergency_keywords"

    ctx_normal = MessageContext(
        core_message=CoreMessageContext(
            message_id="m2",
            raw_text_content="Hey, are we still meeting for lunch?",
            cleaned_text="hey are we still meeting for lunch",
            message_type="TEXT",
            char_count=35,
            word_count=7,
            contains_links=False,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        )
    )
    sig_normal = calc.calculate_signal(ctx_normal)
    assert sig_normal.score < 0.2


def test_payment_urgency_calculator() -> None:
    """Test payment urgency signal calculation for OTP codes vs regular text."""
    calc = PaymentUrgencyCalculator()

    ctx_otp = MessageContext(
        core_message=CoreMessageContext(
            message_id="m3",
            raw_text_content="Your bank OTP code is 948201. Valid for 5 minutes.",
            cleaned_text="your bank otp code is 948201 valid for 5 minutes",
            message_type="TEXT",
            char_count=50,
            word_count=9,
            contains_links=False,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        )
    )
    sig_otp = calc.calculate_signal(ctx_otp)
    assert sig_otp.score == 1.0
    assert sig_otp.explainability.primary_driver == "otp_code"


def test_meeting_urgency_calculator() -> None:
    """Test meeting urgency detection with video meeting link."""
    calc = MeetingUrgencyCalculator()

    ctx_meeting = MessageContext(
        core_message=CoreMessageContext(
            message_id="m4",
            raw_text_content="Starting standup now, join here: https://meet.google.com/abc-def-ghi",
            cleaned_text="starting standup now join here https meet google com abc def ghi",
            message_type="TEXT",
            char_count=65,
            word_count=8,
            contains_links=True,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        )
    )
    sig_meeting = calc.calculate_signal(ctx_meeting)
    assert sig_meeting.score >= 0.8
    assert sig_meeting.explainability.primary_driver == "meeting_link"


def test_spam_scam_risk_calculators() -> None:
    """Test spam, scam, and unknown sender risk calculators."""
    spam_calc = SpamSignalCalculator()
    scam_calc = ScamSignalCalculator()
    unk_calc = UnknownSenderRiskCalculator()

    ctx_scam = MessageContext(
        core_message=CoreMessageContext(
            message_id="m5",
            raw_text_content="Congratulations! You won a lottery prize. Share your OTP code immediately http://scam.link",
            cleaned_text="congratulations you won a lottery prize share your otp code immediately http scam link",
            message_type="TEXT",
            char_count=80,
            word_count=12,
            contains_links=True,
            contains_phone_numbers=False,
            is_forwarded=True,
            forward_count=8,
            is_frequently_forwarded=True,
        ),
        sender=UserContext(
            user_id="unsaved_999",
            display_name="Unknown",
            phone_number="+19998887777",
            user_type="INDIVIDUAL",
            registration_timestamp=0,
            account_age_days=1,
            preferred_language="en",
            timezone="UTC",
            is_verified=False,
            is_registered_user=False,
        ),
        relationship=RelationshipContext(relationship_type="PEER_TO_PEER", is_contacts_saved=False),
    )

    sig_spam = spam_calc.calculate_signal(ctx_scam)
    sig_scam = scam_calc.calculate_signal(ctx_scam)
    sig_unk = unk_calc.calculate_signal(ctx_scam)

    assert sig_spam.score > 0.5
    assert sig_scam.score > 0.5
    assert sig_unk.score == 0.85


def test_known_contact_and_business_trust() -> None:
    """Test trust engine calculators for saved contacts vs unverified business."""
    contact_calc = KnownContactCalculator()
    biz_calc = BusinessTrustCalculator()

    ctx_friend = MessageContext(
        sender=UserContext(
            user_id="u123",
            display_name="Alice",
            phone_number="+123456",
            user_type="INDIVIDUAL",
            registration_timestamp=0,
            account_age_days=500,
            preferred_language="en",
            timezone="UTC",
            is_verified=True,
            is_registered_user=True,
        ),
        relationship=RelationshipContext(relationship_type="PEER_TO_PEER", is_contacts_saved=True),
    )
    assert contact_calc.calculate_signal(ctx_friend).score >= 0.8

    ctx_verified_biz = MessageContext(
        business=BusinessContext(
            business_id="b1",
            business_name="Official Bank",
            category="BANKING",
            verification_status="VERIFIED_OFFICIAL",
            support_email="support@bank.com",
            catalog_enabled=True,
            expected_sla_minutes=5,
            is_business_account=True,
        )
    )
    assert biz_calc.calculate_signal(ctx_verified_biz).score == 1.0


def test_notification_fatigue_calculator() -> None:
    """Test notification fatigue calculator under high daily volume."""
    calc = NotificationFatigueCalculator()

    ctx_fatigue = MessageContext(
        notification_behaviour=NotificationContext(
            user_daily_notification_volume=45,
            historical_open_rate=0.2,
            historical_avg_response_seconds=7200,
            daily_notification_cap=50,
        )
    )
    sig = calc.calculate_signal(ctx_fatigue)
    assert sig.score >= 0.8


def test_greeting_detection_calculator() -> None:
    """Test greeting detection calculator for isolated polite openers."""
    calc = GreetingDetectionCalculator()

    ctx_greeting = MessageContext(
        core_message=CoreMessageContext(
            message_id="m6",
            raw_text_content="Good morning!",
            cleaned_text="good morning",
            message_type="TEXT",
            char_count=13,
            word_count=2,
            contains_links=False,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        )
    )
    sig_g = calc.calculate_signal(ctx_greeting)
    assert sig_g.score == 1.0

    ctx_substantive = MessageContext(
        core_message=CoreMessageContext(
            message_id="m7",
            raw_text_content="Good morning! Please review the attached quarterly revenue report before the meeting.",
            cleaned_text="good morning please review the attached quarterly revenue report before the meeting",
            message_type="TEXT",
            char_count=85,
            word_count=12,
            contains_links=False,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        )
    )
    sig_s = calc.calculate_signal(ctx_substantive)
    assert sig_s.score == 0.0
