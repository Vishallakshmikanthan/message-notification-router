"""End-to-end integration tests for RetrievalEngine 10-Stage Pipeline."""

from datetime import datetime, timezone

from router.application.retrieval.retrieval_engine import RetrievalEngine
from router.domain.entities.context import (
    CoreMessageContext,
    MessageContext,
)
from router.domain.entities.evidence import EvidenceBundle
from router.domain.entities.history import HistoricalMessage
from router.domain.entities.sub_contexts import (
    DEFAULT_BUSINESS_CONTEXT,
    DEFAULT_USER_CONTEXT,
    BusinessContext,
    UserContext,
)
from router.infrastructure.cache.retrieval_cache import RetrievalCache


def test_retrieval_engine_pipeline_end_to_end() -> None:
    """Test full 10-stage retrieval pipeline producing valid EvidenceBundle."""
    engine = RetrievalEngine(retrieval_cache=RetrievalCache())

    msg1 = HistoricalMessage(
        message_id="h_101",
        user_id="user_john",
        sender_id="bank_xyz",
        conversation_type="business",
        message_text="OTP 481920 is your verification code for bank login.",
        created_at=datetime.now(timezone.utc),
        business_id="biz_bank_xyz",
    )
    msg2 = HistoricalMessage(
        message_id="h_102",
        user_id="user_john",
        sender_id="promo_store",
        conversation_type="business",
        message_text="50% off discount sale today! Click here to shop.",
        created_at=datetime.now(timezone.utc),
        business_id="biz_promo",
    )

    engine.index_corpus([msg1, msg2])

    sender_user = UserContext(
        user_id="bank_xyz",
        display_name="Bank XYZ",
        phone_number="180012345",
        user_type="BUSINESS",
        registration_timestamp=0,
        account_age_days=100,
        preferred_language="en",
        timezone="UTC",
        is_verified=True,
    )
    receiver_user = UserContext(
        user_id="user_john",
        display_name="John Doe",
        phone_number="9999999999",
        user_type="INDIVIDUAL",
        registration_timestamp=0,
        account_age_days=300,
        preferred_language="en",
        timezone="UTC",
        is_verified=True,
    )

    biz_ctx = BusinessContext(
        business_id="biz_bank_xyz",
        business_name="Bank XYZ",
        category="BANKING",
        verification_status="VERIFIED_OFFICIAL",
        support_email="support@bankxyz.com",
        catalog_enabled=False,
        expected_sla_minutes=5,
        is_business_account=True,
    )

    context = MessageContext(
        message_id="msg_incoming_001",
        user_id="user_john",
        sender_id="bank_xyz",
        message_text="Please enter OTP 481920 to authorize transaction",
        conversation_type="business",
        sender=sender_user,
        receiver=receiver_user,
        business=biz_ctx,
        core_message=CoreMessageContext(
            message_id="msg_incoming_001",
            raw_text_content="Please enter OTP 481920 to authorize transaction",
            cleaned_text="Please enter OTP 481920 to authorize transaction",
            message_type="TEXT",
            char_count=52,
            word_count=7,
            contains_links=False,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        ),
    )

    bundle = engine.retrieve_evidence(context)

    assert isinstance(bundle, EvidenceBundle)
    assert bundle.query_message_id == "msg_incoming_001"
    assert bundle.user_id == "user_john"
    assert bundle.evidence_count >= 1
    assert bundle.retrieval_confidence > 0.0
    assert bundle.items[0].message_id == "h_101"
    assert bundle.items[0].reason_retrieved in ["PREVIOUS_OTP_REQUEST", "SIMILAR_HISTORICAL_MESSAGE"]


def test_retrieval_engine_caching() -> None:
    """Test that second call retrieves bundle directly from retrieval cache."""
    cache = RetrievalCache()
    engine = RetrievalEngine(retrieval_cache=cache)

    msg = HistoricalMessage(
        message_id="h_201",
        user_id="user_mary",
        sender_id="friend_alice",
        conversation_type="personal",
        message_text="Hey Mary, see you at 6 PM for dinner!",
        created_at=datetime.now(timezone.utc),
    )

    engine.index_corpus([msg])

    context = MessageContext(
        message_id="msg_repeat_01",
        user_id="user_mary",
        sender_id="friend_alice",
        message_text="See you at 6 PM for dinner",
    )

    bundle1 = engine.retrieve_evidence(context)
    bundle2 = engine.retrieve_evidence(context)

    assert bundle1.query_message_id == bundle2.query_message_id
    assert bundle1.evidence_count == bundle2.evidence_count
    assert cache._hits == 1
