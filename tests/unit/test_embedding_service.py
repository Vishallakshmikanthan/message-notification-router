"""Unit tests for EmbeddingService and FAISSIndexWrapper."""

from datetime import UTC, datetime

from router.application.retrieval.embedding_service import EmbeddingService
from router.domain.entities.history import HistoricalMessage
from router.infrastructure.cache.embedding_cache import EmbeddingCache


def test_embedding_generation_and_cache() -> None:
    """Test embedding generation and query LRU caching."""
    cache = EmbeddingCache(max_lru_size=10)
    service = EmbeddingService(embedding_cache=cache, dimension=384)

    text = "Payment confirmation of Rs. 500"
    vec1 = service.generate_embedding(text)
    assert len(vec1) == 384

    # Second call should hit LRU cache
    vec2 = service.generate_embedding(text)
    assert vec1 == vec2
    assert cache.hit_rate > 0.0


def test_vector_indexing_and_search() -> None:
    """Test indexing vectors and performing dense nearest neighbor search."""
    service = EmbeddingService(dimension=384)

    msg1 = HistoricalMessage(
        message_id="h_001",
        user_id="user_1",
        sender_id="bank_official",
        conversation_type="business",
        message_text="Your account has been debited by Rs. 1500 for order #991.",
        created_at=datetime.now(UTC),
    )
    msg2 = HistoricalMessage(
        message_id="h_002",
        user_id="user_1",
        sender_id="friend_john",
        conversation_type="personal",
        message_text="Are we playing football this Sunday at 5 PM?",
        created_at=datetime.now(UTC),
    )

    service.index_vectors([msg1, msg2])

    query_vec = service.generate_embedding("bank account debited order")
    results = service.search(query_vec, top_k=5)

    assert len(results) == 2
    assert results[0].message_id == "h_001"
    assert results[0].dense_score > 0.0
