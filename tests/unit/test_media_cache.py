"""Unit tests for 5-Tier MediaCache content-addressing, lookup/write, and TTL eviction."""

from router.domain.entities.media_context import OCRResult, TextBlock
from router.infrastructure.media.media_cache import MediaCache


def test_media_cache_5_tiers() -> None:
    cache = MediaCache(ttl_seconds=3600)
    sample_hash = "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0"

    # Tier 1: Content
    cache.set_content(sample_hash, b"raw_image_bytes")
    assert cache.get_content(sample_hash) == b"raw_image_bytes"

    # Tier 2: OCR
    ocr_result = OCRResult(
        full_extracted_text="SAMPLE TEXT",
        mean_confidence=0.95,
        text_blocks=[TextBlock(block_id=1, text="SAMPLE TEXT", confidence=0.95, bounding_box=[0, 0, 1, 1])],
        engine_used="PADDLEOCR",
    )
    cache.set_ocr(sample_hash, ocr_result)
    retrieved_ocr = cache.get_ocr(sample_hash)
    assert retrieved_ocr is not None
    assert retrieved_ocr.full_extracted_text == "SAMPLE TEXT"

    # Tier 3: Transcript
    cache.set_transcript(sample_hash, {"transcript": "Hello world", "confidence": 0.98})
    t_data = cache.get_transcript(sample_hash)
    assert t_data is not None and t_data["transcript"] == "Hello world"

    # Tier 4: VLM
    cache.set_vlm(sample_hash, {"scene": "Document page"})
    v_data = cache.get_vlm(sample_hash)
    assert v_data is not None and v_data["scene"] == "Document page"

    # Tier 5: Summary
    cache.set_summary(sample_hash, {"summary": "Payment receipt summary"})
    s_data = cache.get_summary(sample_hash)
    assert s_data is not None and s_data["summary"] == "Payment receipt summary"


def test_media_cache_miss_and_expiration() -> None:
    cache = MediaCache(ttl_seconds=-1)  # Expired instantly
    sample_hash = "expired_hash_123"

    cache.set_content(sample_hash, b"bytes")
    assert cache.get_content(sample_hash) is None  # Should return None due to TTL expiration
