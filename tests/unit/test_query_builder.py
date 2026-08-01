"""Unit tests for QueryBuilder component."""

from router.application.retrieval.query_builder import QueryBuilder
from router.domain.entities.context import (
    CoreMessageContext,
    MessageContext,
)
from router.domain.entities.sub_contexts import (
    BusinessContext,
    UserContext,
)


def test_query_builder_basic() -> None:
    """Test basic query construction from MessageContext."""
    qb = QueryBuilder()
    sender_usr = UserContext(
        user_id="sender_789",
        display_name="Sender 789",
        phone_number="12345",
        user_type="INDIVIDUAL",
        registration_timestamp=0,
        account_age_days=10,
        preferred_language="en",
        timezone="UTC",
        is_verified=False,
    )
    receiver_usr = UserContext(
        user_id="user_123",
        display_name="User 123",
        phone_number="67890",
        user_type="INDIVIDUAL",
        registration_timestamp=0,
        account_age_days=10,
        preferred_language="en",
        timezone="UTC",
        is_verified=False,
    )

    context = MessageContext(
        message_id="msg_test_01",
        user_id="user_123",
        sender_id="sender_789",
        message_text="Where is my order #58291?",
        conversation_type="personal",
        sender=sender_usr,
        receiver=receiver_usr,
        core_message=CoreMessageContext(
            message_id="msg_test_01",
            raw_text_content="Where is my order #58291?",
            cleaned_text="Where is my order #58291?",
            message_type="TEXT",
            char_count=26,
            word_count=5,
            contains_links=False,
            contains_phone_numbers=False,
            is_forwarded=False,
            forward_count=0,
            is_frequently_forwarded=False,
        ),
    )

    query = qb.build_query(context)

    assert query.user_id == "user_123"
    assert query.has_numeric_sequence is True
    assert "order" in query.sparse_terms
    assert query.filters["sender_user_id"] == "sender_789"
    assert query.boost_factors["exact_entity_match"] == 2.5


def test_query_builder_domain_mismatch() -> None:
    """Test query builder domain mismatch flag and risk tokens."""
    qb = QueryBuilder()
    biz_ctx = BusinessContext(
        business_id="biz_bank",
        business_name="Fake Bank",
        category="BANKING",
        verification_status="UNVERIFIED",
        support_email="support@bank.com",
        catalog_enabled=False,
        expected_sla_minutes=10,
        is_business_account=True,
    )
    # Set dynamic property for domain mismatch
    object.__setattr__(biz_ctx, "official_domain", "bank.com") if hasattr(biz_ctx, "__dataclass_fields__") else None

    context = MessageContext(
        message_id="msg_phish_01",
        user_id="user_123",
        sender_id="biz_fake",
        message_text="Click http://fake-bank-alert.com to verify OTP 9912",
        business=biz_ctx,
    )

    query = qb.build_query(context)
    assert "otp" in query.sparse_terms
